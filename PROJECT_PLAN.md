# SafeHealth — Project Plan

## Project Overview

**SafeHealth** is a privacy-first, multi-agent AI concierge for family medication management. It tracks medication schedules, logs dose intake, and checks drug interactions — all while keeping health data local and never sending it to the public cloud.

Target: Kaggle AI Agent Hackathon submission demonstrating ADK-style graph workflows, MCP tool servers, and layered security design.

---

## Current State (as of 2026-06-20)

### What Exists

| Component | File(s) | Status |
|---|---|---|
| Flask API backend | `app.py` | Working skeleton |
| Multi-agent graph workflow | `workflow/graph.py` | Working (rule-based, no LLM) |
| Python MCP tool server | `mcp_server/server.py` | Working (direct import, not stdio) |
| TypeScript MCP server | `mcp_server/src/index.ts` | Implemented, not wired up |
| Data vault | `data/secure_health_vault.json` | 2 members, basic blacklist |
| Frontend UI | `ui/index.html`, `ui/style.css`, `ui/script.js` | Working chat + schedule view |
| Security docs | `docs/security_guardrails.md` | Written |

### Critical Gaps

1. **No LLM integration** — intent routing and responses are pure regex/keyword rules, not AI-powered.
2. **MCP protocol bypassed** — the Python workflow imports `mcp_server/server.py` as a module directly instead of communicating through the actual MCP stdio/JSON-RPC protocol.
3. **No `requirements.txt`** — project cannot be reproduced by a judge or reviewer.
4. **No `README.md`** — missing setup instructions and demo narrative.
5. **No daily reset** — `taken_today` flags persist forever; no midnight reset mechanism.
6. **Thin data vault** — only 2 family members and a small interaction blacklist.
7. **No test files** — no automated verification of core logic.
8. **No log history view** — UI shows today's schedule but not past dose history.

---

## Architecture Target

```
[User Input]
     │
     ▼
[1. Gatekeeper Node]  ←── Regex/script-level, no LLM (intentional security boundary)
     │
     ├─(EMERGENCY)──► Static hardcoded 911 alert
     ├─(UNSAFE)─────► SafetyFallback node
     │
     ▼
[2. Orchestrator Node]  ←── Claude API call for intent classification
     │
     ├─► [3a. Log & Schedule Agent]     ─── calls MCP tool: log_medication_intake
     └─► [3b. Interaction Check Agent]  ─── calls MCP tool: check_interaction
              │
              ▼
     [Local MCP Server]  ←── reads/writes secure_health_vault.json
              │
              ▼
     [Response Node]  ←── Claude API call to format natural language reply
```

---

## Implementation Phases

### Phase 1: Dependency & Dev Environment Setup
**Goal:** Any reviewer can clone and run the project in under 5 minutes.

- [ ] Create `requirements.txt` with pinned versions: `flask`, `flask-cors`, `anthropic`
- [ ] Create `.env.example` with `ANTHROPIC_API_KEY=` placeholder
- [ ] Add `python-dotenv` to requirements and load in `app.py`
- [ ] Verify `mcp_server/package.json` has all correct deps and `npm install` works
- [ ] Add a `run.sh` startup script that starts the Flask server

**Files to create/edit:** `requirements.txt`, `.env.example`, `run.sh`, `app.py`

---

### Phase 2: Real LLM Integration (Claude API)
**Goal:** Replace keyword matching with genuine AI-powered intent classification and natural language response generation.

#### 2a. Intent Classification (Orchestrator Node)
Replace the `route_intent()` function's keyword list with a Claude API call:
- Send user input to `claude-haiku-4-5-20251001` (fast, cheap) with a system prompt listing the four intents: `greeting`, `get_profile`, `check_interaction`, `log_intake`
- Parse the returned intent label
- Keep the Gatekeeper as pure Python regex (never LLM — it's the security boundary)

**File:** `workflow/graph.py` — `route_intent()` function

#### 2b. Natural Language Response Generation (Response Node)
Replace hardcoded f-string responses in `run_mcp_tool()` with a Claude API call:
- Feed Claude the structured MCP tool result (JSON) plus user's original query
- Instruct Claude to produce a concise, warm, factual reply
- System prompt enforces the clinical boundary rules from `docs/security_guardrails.md`

**File:** `workflow/graph.py` — `run_mcp_tool()` function, new `format_response()` helper

#### 2c. Anthropic Client Setup
- Add a singleton `anthropic.Anthropic()` client initialized once at module level
- Use `ANTHROPIC_API_KEY` from environment

**File:** `workflow/graph.py`

---

### Phase 3: True MCP Protocol Wiring
**Goal:** The agent communicates with the data layer through the actual MCP protocol, not a direct Python import, satisfying the hackathon's MCP component requirement.

#### Option A (Recommended for hackathon scope): subprocess MCP bridge
- In `workflow/graph.py`, instead of `from mcp_server import server`, spawn the Python MCP server as a subprocess
- Send JSON-RPC requests over stdin, read responses from stdout
- `mcp_server/server.py` already has a `main()` stdio loop — use it

#### Option B: Full TypeScript MCP server
- Build the TypeScript server (`npm run build` in `mcp_server/`)
- Spawn `node mcp_server/build/index.js` as a subprocess from Python
- This is the "proper" MCP SDK path but adds Node.js as a runtime dependency

**Recommended:** Implement Option A first to unblock Phases 4–5, then add Option B as a bonus if time allows.

**File:** `workflow/graph.py` — new `MCPClient` class wrapping subprocess communication

---

### Phase 4: Data Vault Expansion
**Goal:** Make the demo richer and more convincing for judges.

- [ ] Add 2 more family members: `member_03` (teenager, e.g. vitamins), `member_04` (elderly grandparent, e.g. warfarin, metformin)
- [ ] Expand `interaction_blacklist` to 8–10 drug pairs (e.g., Warfarin + Aspirin, Metformin + Alcohol, SSRIs + MAOIs)
- [ ] Add a `reset_daily_flags()` utility function that sets all `taken_today` back to `false` (called on server startup or via a cron endpoint)
- [ ] Add a `conditions` field per member (e.g., hypertension, diabetes) to make interaction warnings richer

**File:** `data/secure_health_vault.json`, `mcp_server/server.py`

---

### Phase 5: UI Polish
**Goal:** The UI should visually demonstrate the security model and multi-member switching.

- [ ] Show "Switching to [Name]'s secure profile…" toast on member card click
- [ ] Add a log history panel that calls a new `GET /api/logs/<member_id>` endpoint
- [ ] Display `⚠️` warning badge on interaction results in chat
- [ ] Add a "Security" indicator in the header that turns red on any blocked/fallback response
- [ ] Show typing indicator while waiting for LLM response

**Files:** `ui/index.html`, `ui/script.js`, `ui/style.css`, `app.py`

---

### Phase 6: Hardening & Edge Cases
**Goal:** Ensure the security claims actually hold under adversarial testing.

- [ ] Expand Gatekeeper injection patterns (add: `"act as"`, `"pretend you are"`, `"DAN"`, `"jailbreak"`)
- [ ] Expand emergency keywords (add: `"unresponsive"`, `"not breathing"`, `"allergic reaction"`, `"seizure"`)
- [ ] Add cross-member authorization check: verify `sender_id` cannot request data for another `member_id` unless a `guardian` relationship is defined in the vault
- [ ] Wrap `write_vault()` with a file lock to prevent concurrent write corruption
- [ ] Cap log array size to prevent unbounded file growth (keep last 1000 entries)

**Files:** `workflow/graph.py`, `mcp_server/server.py`, `data/secure_health_vault.json`

---

### Phase 7: Testing
**Goal:** Basic smoke tests to prove the architecture works end-to-end.

- [ ] `tests/test_gatekeeper.py` — assert EMERGENCY and UNSAFE cases short-circuit correctly
- [ ] `tests/test_mcp_tools.py` — unit test each MCP function against known vault data
- [ ] `tests/test_interactions.py` — assert known blacklisted pairs return `has_interaction: true`
- [ ] `tests/test_workflow.py` — end-to-end: safe input → intent → tool → response (mocked LLM)

**Files:** `tests/` directory (new)

---

### Phase 8: Documentation & Submission
**Goal:** A judge who has never seen the repo can understand, run, and evaluate it in 10 minutes.

- [ ] Write `README.md`: project summary, architecture diagram (ASCII), setup steps, example queries
- [ ] Update `docs/security_guardrails.md` with the final Gatekeeper pattern list
- [ ] Add inline comments to `workflow/graph.py` for the three non-obvious invariants (why the Gatekeeper is LLM-free, why intent and response are separate Claude calls, why MCP is a subprocess not a module import)
- [ ] Record a 2-minute screen demo: greeting → schedule view → interaction check → log dose → blocked emergency → prompt injection attempt

---

## Priority Order

```
Phase 1 (Setup)  →  Phase 2 (LLM)  →  Phase 3 (MCP)  →  Phase 4 (Data)
     then:
Phase 6 (Hardening)  →  Phase 7 (Tests)  →  Phase 5 (UI Polish)  →  Phase 8 (Docs)
```

Phases 1–3 are blockers. Without them, the project cannot credibly claim ADK + MCP + AI. Phases 4–6 are differentiators. Phases 7–8 are polish.

---

## Key Technical Decisions

| Decision | Choice | Reason |
|---|---|---|
| LLM for Gatekeeper? | **No** — pure regex | LLMs can be jailbroken; the security boundary must be deterministic |
| LLM model for intent | `claude-haiku-4-5-20251001` | Speed and cost; intent classification doesn't need reasoning |
| LLM model for response | `claude-sonnet-4-6` | Better language quality for the user-facing reply |
| MCP protocol | stdio JSON-RPC subprocess | Matches MCP spec; keeps data layer isolated from agent layer |
| Data storage | Local JSON file | Privacy-first constraint; no cloud DB |
| Auth model | `sender_id` token in request | Simple; sufficient for hackathon; extensible to JWT |

---

## File Structure (Target)

```
safe_health/
├── app.py                        # Flask API entry point
├── requirements.txt              # Python dependencies (NEW)
├── .env.example                  # API key template (NEW)
├── run.sh                        # One-command startup (NEW)
├── PROJECT_PLAN.md               # This file
├── README.md                     # Public-facing docs (NEW)
├── data/
│   └── secure_health_vault.json  # Encrypted local health data
├── docs/
│   └── security_guardrails.md   # Security rules reference
├── mcp_server/
│   ├── __init__.py
│   ├── server.py                 # Python MCP stdio server
│   ├── package.json              # TypeScript MCP server deps
│   ├── tsconfig.json
│   └── src/
│       └── index.ts              # TypeScript MCP server (bonus)
├── tests/                        # NEW
│   ├── test_gatekeeper.py
│   ├── test_mcp_tools.py
│   ├── test_interactions.py
│   └── test_workflow.py
├── ui/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── workflow/
    ├── __init__.py
    └── graph.py                  # Multi-agent workflow graph
```
