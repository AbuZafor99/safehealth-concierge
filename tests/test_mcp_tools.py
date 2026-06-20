"""Tests for MCP server tool functions using an isolated copy of the vault."""
import json
import pytest
import mcp_server.server as srv


# ── Profile retrieval ──────────────────────────────────────────────────────

def test_get_profile_returns_correct_member(vault_path):
    result = srv.get_family_member_profile("member_01")
    assert result["name"] == "Sarah (Mom)"
    assert "Lisinopril" in result["current_medications"]
    assert "schedule" in result


def test_get_profile_returns_all_four_members(vault_path):
    for mid, expected_name in [
        ("member_01", "Sarah (Mom)"),
        ("member_02", "Alex (Dad)"),
        ("member_03", "Jake (Teen Son)"),
        ("member_04", "Gran (Grandma)"),
    ]:
        result = srv.get_family_member_profile(mid)
        assert result["name"] == expected_name, f"Wrong name for {mid}"


def test_get_profile_unknown_member_returns_error(vault_path):
    result = srv.get_family_member_profile("member_99")
    assert "error" in result
    assert "member_99" in result["error"]


# ── Permission enforcement ─────────────────────────────────────────────────

def test_cross_member_access_denied(vault_path):
    # Alex (member_02) has no can_view relationship — cannot read Sarah
    result = srv.get_family_member_profile("member_01", requester_id="member_02")
    assert "error" in result
    assert "denied" in result["error"].lower()


def test_guardian_access_allowed(vault_path):
    # Sarah (member_01) has can_view: [member_02, member_03, member_04]
    result = srv.get_family_member_profile("member_04", requester_id="member_01")
    assert result["name"] == "Gran (Grandma)"


def test_self_access_always_allowed(vault_path):
    result = srv.get_family_member_profile("member_01", requester_id="member_01")
    assert result["name"] == "Sarah (Mom)"


# ── Medication logging ─────────────────────────────────────────────────────

def test_log_intake_sets_taken_today(vault_path):
    srv.log_medication_intake("member_01", "Lisinopril")
    profile = srv.get_family_member_profile("member_01")
    lisinopril = next(s for s in profile["schedule"] if s["medication"] == "Lisinopril")
    assert lisinopril["taken_today"] is True


def test_log_intake_writes_to_logs_array(vault_path):
    srv.log_medication_intake("member_04", "Warfarin")
    logs = srv.get_logs("member_04")["logs"]
    assert len(logs) == 1
    assert logs[0]["medication"] == "Warfarin"
    assert logs[0]["status"] == "taken"
    assert "timestamp" in logs[0]


def test_log_intake_unknown_member_returns_error(vault_path):
    result = srv.log_medication_intake("member_99", "Aspirin")
    assert "error" in result


def test_log_intake_case_insensitive_match(vault_path):
    srv.log_medication_intake("member_01", "lisinopril")  # lowercase
    profile = srv.get_family_member_profile("member_01")
    lisinopril = next(s for s in profile["schedule"] if s["medication"] == "Lisinopril")
    assert lisinopril["taken_today"] is True


# ── Daily reset ────────────────────────────────────────────────────────────

def test_reset_clears_all_taken_today_flags(vault_path):
    # Log some doses first
    srv.log_medication_intake("member_01", "Lisinopril")
    srv.log_medication_intake("member_04", "Warfarin")

    result = srv.reset_daily_flags()
    assert result["status"] == "reset"
    assert result["schedule_items_reset"] == 9  # total across all 4 members

    # Verify every flag is now False
    import json, os
    vault = json.loads(open(srv.DATA_PATH).read())
    for member in vault["family_members"].values():
        for item in member["schedule"]:
            assert item["taken_today"] is False, f"Flag still set for {item['medication']}"


def test_reset_returns_correct_count(vault_path):
    result = srv.reset_daily_flags()
    assert result["schedule_items_reset"] == 9


# ── Log retrieval ──────────────────────────────────────────────────────────

def test_get_logs_returns_only_member_logs(vault_path):
    srv.log_medication_intake("member_01", "Lisinopril")
    srv.log_medication_intake("member_04", "Warfarin")

    logs_01 = srv.get_logs("member_01")["logs"]
    assert all(l["member_id"] == "member_01" for l in logs_01)

    logs_04 = srv.get_logs("member_04")["logs"]
    assert all(l["member_id"] == "member_04" for l in logs_04)


def test_get_logs_returns_at_most_10(vault_path):
    for _ in range(15):
        srv.log_medication_intake("member_01", "Lisinopril")
    logs = srv.get_logs("member_01")["logs"]
    assert len(logs) <= 10


# ── add_medication ─────────────────────────────────────────────────────────

def test_add_medication_appears_in_profile(vault_path):
    srv.add_medication("member_01", "Metoprolol", "25mg", "08:00 AM")
    profile = srv.get_family_member_profile("member_01")
    assert "Metoprolol" in profile["current_medications"]
    sched = next((s for s in profile["schedule"] if s["medication"] == "Metoprolol"), None)
    assert sched is not None
    assert sched["dosage"] == "25mg"
    assert sched["time"] == "08:00 AM"
    assert sched["taken_today"] is False


def test_add_medication_rejects_duplicate(vault_path):
    result = srv.add_medication("member_01", "Lisinopril", "10mg", "08:00 AM")
    assert "error" in result
    assert "already" in result["error"].lower()


def test_add_medication_unknown_member_returns_error(vault_path):
    result = srv.add_medication("member_99", "Aspirin", "81mg", "08:00 AM")
    assert "error" in result


# ── remove_medication ──────────────────────────────────────────────────────

def test_remove_medication_drops_from_profile(vault_path):
    srv.add_medication("member_01", "TempDrug", "5mg", "12:00 PM")
    srv.remove_medication("member_01", "TempDrug")
    profile = srv.get_family_member_profile("member_01")
    assert "TempDrug" not in profile["current_medications"]
    assert all(s["medication"] != "TempDrug" for s in profile["schedule"])


def test_remove_medication_not_found_returns_error(vault_path):
    result = srv.remove_medication("member_01", "NonExistentDrug")
    assert "error" in result


def test_remove_medication_unknown_member_returns_error(vault_path):
    result = srv.remove_medication("member_99", "Lisinopril")
    assert "error" in result


# ── update_medication ──────────────────────────────────────────────────────

def test_update_medication_changes_dosage(vault_path):
    srv.update_medication("member_01", "Lisinopril", new_dosage="20mg")
    profile = srv.get_family_member_profile("member_01")
    sched = next(s for s in profile["schedule"] if s["medication"] == "Lisinopril")
    assert sched["dosage"] == "20mg"
    assert sched["time"] == "08:00 AM"  # unchanged


def test_update_medication_changes_time(vault_path):
    srv.update_medication("member_01", "Lisinopril", new_time="09:00 PM")
    profile = srv.get_family_member_profile("member_01")
    sched = next(s for s in profile["schedule"] if s["medication"] == "Lisinopril")
    assert sched["time"] == "09:00 PM"
    assert sched["dosage"] == "10mg"  # unchanged


def test_update_medication_changes_both_fields(vault_path):
    srv.update_medication("member_01", "Lisinopril", new_dosage="20mg", new_time="09:00 PM")
    profile = srv.get_family_member_profile("member_01")
    sched = next(s for s in profile["schedule"] if s["medication"] == "Lisinopril")
    assert sched["dosage"] == "20mg"
    assert sched["time"] == "09:00 PM"


def test_update_medication_not_found_returns_error(vault_path):
    result = srv.update_medication("member_01", "FakeDrug", new_dosage="5mg")
    assert "error" in result


# ── evaluate_daily_log_safety ──────────────────────────────────────────────

def test_daily_log_safety_safe_when_nothing_taken(vault_path):
    result = srv.evaluate_daily_log_safety("member_01", "Lisinopril")
    assert result["safe"] is True
    assert result["taken_today"] == []


def test_daily_log_safety_blocks_known_interaction(vault_path):
    srv.log_medication_intake("member_04", "Warfarin")
    result = srv.evaluate_daily_log_safety("member_04", "Aspirin")
    assert result["safe"] is False
    assert "Warfarin" in result["conflicts"]
    assert "WARNING" in result["warning"]


def test_daily_log_safety_allows_non_interacting_combo(vault_path):
    srv.log_medication_intake("member_04", "Metformin")
    result = srv.evaluate_daily_log_safety("member_04", "Atorvastatin")
    # Metformin + Atorvastatin is not in the blacklist
    assert result["safe"] is True


def test_daily_log_safety_symmetric_conflict(vault_path):
    # Log Aspirin first, then check if Warfarin is blocked (reverse direction)
    srv.log_medication_intake("member_04", "Aspirin")
    result = srv.evaluate_daily_log_safety("member_04", "Warfarin")
    assert result["safe"] is False
    assert "Aspirin" in result["conflicts"]


def test_daily_log_safety_unknown_member_returns_error(vault_path):
    result = srv.evaluate_daily_log_safety("member_99", "Aspirin")
    assert "error" in result
