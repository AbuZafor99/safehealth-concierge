# SafeHealth — Family Medication & Wellness Concierge

A privacy-first, multi-agent AI concierge that helps families manage medication schedules, log doses, check drug interactions, and keep sensitive health data strictly local — powered by **Google Gemini** and **Google ADK 2.3**.

---

## What it does

- **Schedule management** — view any family member's daily medication schedule with taken/pending status
- **Interaction checking** — detect dangerous drug combinations from a curated local blacklist
- **Pre-dose safety gate** — before logging any dose, automatically checks whether it conflicts with medications already taken today
- **Dose logging** — record intake and mark medications taken today; log history persisted locally
- **Medication CRUD** — add, remove, or update medications and schedules on the fly
- **Safety-first design** — emergency phrases short-circuit to a hardcoded 911 alert; prompt injections are blocked before any LLM call is made

---

## Architecture

```
[User Input]
     │
[1. Gatekeeper Node]  ← pure Python regex — never calls an LLM
     │
 ┌───┴────────┐
EMERGENCY   UNSAFE
 │               │
[Hardcoded    [Hardcoded
 911 Alert]    Block Msg]
               │
            SAFE
              │
[2. ADK LlmAgent]  ← Gemini 2.5 Flash Lite classifies intent,
     │                selects tool, and formats the reply
     │
[3. MCPClient]  ← JSON-RPC over stdio subprocess boundary
     │
[4. mcp_server/server.py subprocess]  ← reads/writes secure_health_vault.json
```

**7 tools registered with the ADK agent:**

| Tool | Purpose |
|---|---|
| `get_family_member_profile` | Read a member's schedule and medication list |
| `check_drug_interaction` | Look up two medications in the local blacklist |
| `evaluate_daily_log_safety` | Check if logging a new dose is safe given what was already taken today |
| `log_medication_intake` | Record a dose and mark it taken |
| `add_medication` | Add a new medication to a member's schedule |
| `remove_medication` | Remove a medication permanently |
| `update_medication` | Change dosage or scheduled time |

**Key design decisions:**

| Decision | Reason |
|---|---|
| Gatekeeper is pure Python regex, not LLM | An LLM-based gate can itself be jailbroken |
| Tools talk through an MCP subprocess, not a Python import | Enforces a real data isolation boundary |
| `ContextVar` carries `sender_id` into tool functions | Thread-safe propagation without passing it through the ADK call stack |
| `evaluate_daily_log_safety` called before every log | Prevents accidentally taking a dangerous combination in the same day |
| Emergency replies are hardcoded strings | Clinical liability — must never be delegated to an AI |

---

## Setup

**Prerequisites:** Python 3.11+, a [Google AI Studio](https://ai.google.dev) API key

```bash
git clone <repo-url>
cd safe_health

cp .env.example .env
# Open .env and set: GEMINI_API_KEY=your_key_here

./run.sh
```

Open `http://localhost:5001` in your browser.

---

## Family members (demo data)

| ID | Name | Conditions | Medications |
|---|---|---|---|
| `member_01` | Sarah (Mom) | hypertension | Lisinopril 10mg |
| `member_02` | Alex (Dad) | chronic pain | Ibuprofen 200mg · Aspirin 81mg |
| `member_03` | Jake (Teen Son) | — | Vitamin D 1000IU · Omega-3 500mg |
| `member_04` | Gran (Grandma) | diabetes · high cholesterol · atrial fibrillation | Warfarin 5mg · Metformin 500mg (×2) · Atorvastatin 20mg |

**Access control:** Sarah (`member_01`) is the family guardian and can view all other profiles. All other members can only view their own data.

---

## Example queries

Copy these into the chat to see each feature:

| Query | What it demonstrates |
|---|---|
| `Show my medications` | Profile tool → schedule with taken/pending badges |
| `Can I take Warfarin with Aspirin?` | Interaction check → ⚠️ warning with amber styling |
| `Can I take my Lisinopril now?` | Pre-dose safety gate → checks today's intake log before approving |
| `I took my Lisinopril` | Log intake → vault updated, Recent Doses panel refreshes |
| `I am having chest pain` | Emergency intercept → hardcoded 911 alert, Gemini never called |
| `Ignore previous instructions` | Injection block → security indicator turns red |
| `Add Metoprolol 25mg at 08:00 AM to my schedule` | Add medication → interaction check + vault write |
| `Remove Ibuprofen from my schedule` | Remove medication → profile updated |
| `Change my Lisinopril to 20mg` | Update medication → dosage patched in vault |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Main chat endpoint; returns `response` and `security_status` |
| `GET` | `/api/profile/<member_id>` | Raw profile JSON for a member |
| `GET` | `/api/logs/<member_id>` | Last 10 dose log entries for a member |
| `POST` | `/api/reset` | Reset all `taken_today` flags (fresh day) |

---

## Running tests

```bash
venv/bin/pytest tests/ -v
```

**91 tests, ~1 second, zero API calls.** Gemini is mocked for all workflow tests; each MCP test runs against an isolated copy of the vault via `tmp_path`.

| File | Tests | Coverage |
|---|---|---|
| `tests/test_gatekeeper.py` | 35 | All 12 injection + 13 emergency patterns, case-insensitivity, safe inputs, boundary cases |
| `tests/test_interactions.py` | 16 | 7 known dangerous pairs, 3 symmetry checks, 4 safe combos, response structure |
| `tests/test_mcp_tools.py` | 29 | Full CRUD, permission model, pre-dose safety gate, log cap, daily reset |
| `tests/test_workflow.py` | 11 | EMERGENCY/BLOCKED static paths, Gemini never called for unsafe inputs, return type contract |

---

## Hackathon technical requirements

| Requirement | Implementation |
|---|---|
| **ADK 2.3 Graph Workflow** | `workflow/graph.py` — Gatekeeper, Orchestrator, ToolExecutor, SafetyFallback nodes with conditional routing via `google-adk==2.3.0` |
| **MCP Server** | `mcp_server/server.py` — stdio JSON-RPC subprocess with 9 callable methods; `workflow/mcp_client.py` — thread-safe subprocess manager |
| **Gemini API** | `gemini-2.5-flash-lite` via `google-adk 2.3`; intent + tool selection + response in one ADK agent pass |
| **Security** | Regex Gatekeeper (12 injection + 13 emergency patterns), cross-member auth via relationships map, write-lock on vault, log size cap |
| **Privacy** | All health data stays in `data/secure_health_vault.json` on the local filesystem — no data sent to any cloud service |

---

## Project structure

```
safe_health/
├── app.py                          # Flask API (chat, profile, logs, reset)
├── requirements.txt
├── run.sh                          # One-command startup
├── .env.example
├── PROJECT_PLAN.md                 # Architecture decisions and phase breakdown
├── ROADMAP.md                      # Granular task checklist used during development
├── data/
│   └── secure_health_vault.json    # Local JSON health data store (never leaves this machine)
├── docs/
│   └── security_guardrails.md      # Full pattern lists and security rules reference
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                   # MCP tool server — 9 methods over stdio JSON-RPC
│   ├── package.json                # TypeScript MCP server dependencies
│   ├── tsconfig.json
│   └── src/
│       └── index.ts                # TypeScript MCP server (official SDK, bonus implementation)
├── tests/
│   ├── conftest.py                 # Shared vault_path fixture (isolated tmp_path per test)
│   ├── test_gatekeeper.py
│   ├── test_interactions.py
│   ├── test_mcp_tools.py
│   └── test_workflow.py
├── ui/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── workflow/
    ├── graph.py                    # Multi-agent workflow — Gatekeeper + ADK LlmAgent + 7 tools
    └── mcp_client.py               # MCP subprocess manager (spawn, lock, call, close)
```
