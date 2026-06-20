import json
import sys
import os
import threading
from datetime import datetime

DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/secure_health_vault.json")

# Serialises all vault writes; prevents data corruption under concurrent Flask requests.
_write_lock = threading.Lock()


def read_vault():
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def write_vault(vault):
    with _write_lock:
        with open(DATA_PATH, "w") as f:
            json.dump(vault, f, indent=2)


# ── Permission model ─────────────────────────────────────────────────────────

def check_permission(requester_id: str, target_id: str, vault: dict) -> bool:
    """Returns True if requester may access target's profile.

    Access is always granted when requester == target.  Otherwise the
    relationships map is consulted: {"member_01": {"can_view": ["member_02"]}}
    """
    if requester_id == target_id:
        return True
    can_view = vault.get("relationships", {}).get(requester_id, {}).get("can_view", [])
    return target_id in can_view


# ── Tool functions ───────────────────────────────────────────────────────────

def get_family_member_profile(member_id, requester_id=None):
    vault = read_vault()

    if requester_id and requester_id != member_id:
        if not check_permission(requester_id, member_id, vault):
            return {
                "error": (
                    f"Access denied. You are not authorised to view "
                    f"{member_id}'s profile."
                )
            }

    member = vault.get("family_members", {}).get(member_id)
    if not member:
        return {"error": f"Member {member_id} not found."}
    return member


def check_interaction(medication_a, medication_b):
    vault = read_vault()
    blacklist = vault.get("interaction_blacklist", {})

    blacklist_a = blacklist.get(medication_a, [])
    blacklist_b = blacklist.get(medication_b, [])
    conflict = medication_b in blacklist_a or medication_a in blacklist_b

    return {
        "medication_a": medication_a,
        "medication_b": medication_b,
        "has_interaction": conflict,
        "warning": (
            f"WARNING: Potential interaction detected between {medication_a} and {medication_b}!"
            if conflict else
            "No documented interaction found."
        ),
    }


def log_medication_intake(member_id, medication):
    vault = read_vault()
    member = vault.get("family_members", {}).get(member_id)
    if not member:
        return {"error": f"Member {member_id} not found."}

    for item in member.get("schedule", []):
        if item["medication"].lower() == medication.lower():
            item["taken_today"] = True

    log_entry = {
        "member_id": member_id,
        "medication": medication,
        "timestamp": datetime.now().isoformat(),
        "status": "taken",
    }
    logs = vault.setdefault("logs", [])
    logs.append(log_entry)

    # Cap log array to prevent unbounded file growth
    if len(logs) > 1000:
        vault["logs"] = logs[-1000:]

    write_vault(vault)
    return {
        "status": "success",
        "message": f"Successfully logged intake for {medication} (Member: {member_id})",
    }


def add_medication(member_id, medication_name, dosage, time):
    vault = read_vault()
    member = vault.get("family_members", {}).get(member_id)
    if not member:
        return {"error": f"Member {member_id} not found."}

    meds = member.setdefault("current_medications", [])
    if any(m.lower() == medication_name.lower() for m in meds):
        return {"error": f"{medication_name} is already in {member['name']}'s medication list."}

    meds.append(medication_name)
    member.setdefault("schedule", []).append({
        "medication": medication_name,
        "dosage": dosage,
        "time": time,
        "taken_today": False,
    })

    write_vault(vault)
    return {
        "status": "success",
        "message": f"Added {medication_name} ({dosage} at {time}) to {member['name']}'s schedule.",
    }


def remove_medication(member_id, medication_name):
    vault = read_vault()
    member = vault.get("family_members", {}).get(member_id)
    if not member:
        return {"error": f"Member {member_id} not found."}

    original_count = len(member.get("current_medications", []))
    member["current_medications"] = [
        m for m in member.get("current_medications", [])
        if m.lower() != medication_name.lower()
    ]
    member["schedule"] = [
        s for s in member.get("schedule", [])
        if s["medication"].lower() != medication_name.lower()
    ]

    if len(member["current_medications"]) == original_count:
        return {"error": f"{medication_name} was not found in {member['name']}'s medications."}

    write_vault(vault)
    return {
        "status": "success",
        "message": f"Removed {medication_name} from {member['name']}'s schedule.",
    }


def update_medication(member_id, medication_name, new_dosage=None, new_time=None):
    vault = read_vault()
    member = vault.get("family_members", {}).get(member_id)
    if not member:
        return {"error": f"Member {member_id} not found."}

    updated = False
    for item in member.get("schedule", []):
        if item["medication"].lower() == medication_name.lower():
            if new_dosage:
                item["dosage"] = new_dosage
            if new_time:
                item["time"] = new_time
            updated = True

    if not updated:
        return {"error": f"{medication_name} was not found in {member['name']}'s schedule."}

    write_vault(vault)
    changes = []
    if new_dosage:
        changes.append(f"dosage → {new_dosage}")
    if new_time:
        changes.append(f"time → {new_time}")
    return {
        "status": "success",
        "message": f"Updated {medication_name} for {member['name']}: {', '.join(changes)}.",
    }


def evaluate_daily_log_safety(member_id, new_medication):
    vault = read_vault()
    member = vault.get("family_members", {}).get(member_id)
    if not member:
        return {"error": f"Member {member_id} not found."}

    today = datetime.now().date().isoformat()

    # Union of schedule flags and today's log timestamps — handles off-schedule intakes.
    from_schedule = {
        item["medication"]
        for item in member.get("schedule", [])
        if item.get("taken_today")
    }
    from_logs = {
        log["medication"]
        for log in vault.get("logs", [])
        if log.get("member_id") == member_id and log.get("timestamp", "").startswith(today)
    }
    taken_today = list((from_schedule | from_logs) - {new_medication})

    blacklist = vault.get("interaction_blacklist", {})
    conflicts = [
        med for med in taken_today
        if med in blacklist.get(new_medication, []) or new_medication in blacklist.get(med, [])
    ]

    if conflicts:
        return {
            "safe": False,
            "conflicts": conflicts,
            "warning": (
                f"WARNING: {new_medication} has a known interaction with "
                f"{', '.join(conflicts)}, which you already took today. "
                "Consult your doctor before taking this dose."
            ),
        }
    return {
        "safe": True,
        "taken_today": taken_today,
        "message": (
            f"No interactions found between {new_medication} and today's active medications"
            f" ({', '.join(taken_today) if taken_today else 'none taken yet'})."
        ),
    }


def reset_daily_flags():
    vault = read_vault()
    count = 0
    for member in vault.get("family_members", {}).values():
        for item in member.get("schedule", []):
            item["taken_today"] = False
            count += 1
    write_vault(vault)
    return {"status": "reset", "schedule_items_reset": count}


def get_logs(member_id):
    vault = read_vault()
    all_logs = vault.get("logs", [])
    member_logs = [l for l in all_logs if l.get("member_id") == member_id]
    return {"logs": member_logs[-10:]}


# ── Request router ───────────────────────────────────────────────────────────

def process_request(req):
    method = req.get("method")
    params = req.get("params", {})

    if method == "get_family_member_profile":
        return get_family_member_profile(
            params.get("member_id"),
            requester_id=params.get("requester_id"),
        )
    elif method == "check_interaction":
        return check_interaction(params.get("medication_a"), params.get("medication_b"))
    elif method == "log_medication_intake":
        return log_medication_intake(params.get("member_id"), params.get("medication"))
    elif method == "remove_medication":
        return remove_medication(params.get("member_id"), params.get("medication_name"))
    elif method == "update_medication":
        return update_medication(
            params.get("member_id"),
            params.get("medication_name"),
            params.get("new_dosage"),
            params.get("new_time"),
        )
    elif method == "evaluate_daily_log_safety":
        return evaluate_daily_log_safety(params.get("member_id"), params.get("new_medication"))
    elif method == "add_medication":
        return add_medication(
            params.get("member_id"),
            params.get("medication_name"),
            params.get("dosage"),
            params.get("time"),
        )
    elif method == "reset_daily_flags":
        return reset_daily_flags()
    elif method == "get_logs":
        return get_logs(params.get("member_id"))
    else:
        return {"error": "Method not found"}


# ── Stdio MCP loop ───────────────────────────────────────────────────────────

def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
            result = process_request(req)
            print(json.dumps({"result": result}))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Profile member_01:", get_family_member_profile("member_01"))
        print("Interaction Lisinopril/Ibuprofen:", check_interaction("Lisinopril", "Ibuprofen"))
        vault = read_vault()
        print("Alex→Sarah perm:", check_permission("member_02", "member_01", vault))
        print("Sarah→Gran perm:", check_permission("member_01", "member_04", vault))
    else:
        main()
