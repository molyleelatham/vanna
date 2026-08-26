# Vanna Hackathon — Completion TODO

**Last updated:** 2026-08-26  
**Status:** ✅ **Priority 1 DONE** — OrchestratorAgent wired, 6-agent chain running, GovernanceAgent produces final decision  
**Remaining:** Priority 2 (prompts), Priority 3 (tests), Priority 4 (SuperGrid + AMD), Priority 5 (metrics)

---

## ✅ COMPLETE (Priority 1 — Critical Path)

| Component | Verification |
|-----------|--------------|
| Federation FAB (5 desks, FedAvg, 3 rounds) | `uv run flwr run . --federation-config="num-supernodes=5" --stream` ✓ |
| Agent FAB (7 typed agent roles incl. Orchestrator) | `uv run flwr build` ✓ |
| Core domain: schemas, privacy, deterministic decisioning | `uv run pytest -q` (13 passed) ✓ |
| Local deterministic demo (no federation/model needed) | `uv run python scripts/local_demo.py` ✓ |
| Artifact sync (federation → agent) | `uv run python scripts/sync_federation_artifact.py` ✓ |
| Safety invariants enforced | Privacy checks, no auto-execution/blacklist ✓ |
| **OrchestratorAgent sequencing all 6 agents** | `apps/agent/vanna_agent/agents/orchestrator.py` ✓ |
| **AgentApp calls orchestrator (MAX_AGENT_CALLS=6)** | `apps/agent/vanna_agent/agent_app.py` ✓ |
| **Full governance output in demo** | `Governance: HUMAN_REVIEW — one or more independent agent review controls triggered` ✓ |

---

## 🎯 DEMO NOW WORKS END-TO-END (Local Path)

```bash
cd apps/federation
uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../..
uv run python scripts/sync_federation_artifact.py
uv run python scripts/local_demo.py
```

Output includes all 6 agents + final Governance decision.

---

## ⚠️ REMAINING WORK (Priorities 2–5)

| Priority | Task | Status | Effort |
|----------|------|--------|--------|
| **2.1** | Add `explain()` methods to each agent for LLM narration | ⬜ Not started | Low |
| **2.2** | Structured handoff payloads between agents | ⬜ Not started | Low |
| **2.3** | Orchestrator streams each agent's contribution | ⬜ Not started | Low |
| **3.1** | Timeout/retries for model calls | ⬜ Not started | Medium |
| **3.2** | Test malformed agent outputs caught | ⬜ Not started | Medium |
| **3.3** | Test child-agent failure → deterministic fallback | ⬜ Not started | Medium |
| **4.1** | Configure AMD model endpoint env vars | ⬜ Not started | Medium (infra) |
| **4.2** | Start local SuperLink: `uv run flower-superlink --insecure` | ⬜ Not started | Medium (infra) |
| **4.3** | Run AgentApp on SuperGrid `@molyleela/Vanna` | ⬜ Not started | Medium (infra) |
| **5.1** | Capture federation round times, loss improvement | ⬜ Not started | Low |
| **5.2** | Capture AgentApp latency (with/without model) | ⬜ Not started | Low |
| **5.3** | Update README demo flow with measured numbers | ⬜ Not started | Low |

---

## 👥 WORKSTREAM OWNERSHIP

| Workstream | Owner | Scope |
|------------|-------|-------|
| **Prompts + streaming** (Priority 2) | Moly | Tasks 2.1–2.3 |
| **Integration tests** (Priority 3) | Moly | Tasks 3.1–3.3 |
| **SuperGrid + AMD** (Priority 4) | Melanie | Tasks 4.1–4.3 (needs 5 SuperNodes) |
| **Demo metrics** (Priority 5) | Moly | Tasks 5.1–5.3 |

---

## 📋 NEXT ACTIONS FOR MOLY (Priority 2 & 3)

### Priority 2: Refine LLM Prompts (Demo Polish)
1. Add `explain(self, ...)` method to each agent in `apps/agent/vanna_agent/agents/*.py`
2. Update `OrchestratorAgent.assess()` to collect and stream each agent's explanation
3. Update `agent_app.py` to use structured streaming handoffs

### Priority 3: Integration Tests (Reliability)
1. Add timeout/retries to `OpenAI` client in `agent_app.py`
2. Add test: malformed agent output → validation error caught
3. Add test: child agent exception → deterministic fallback triggered

### Priority 5: Demo Metrics (Delivery)
1. Time federation run (`date` before/after)
2. Time AgentApp local demo
3. Update README with measured numbers

---

## 📋 NEXT ACTIONS FOR MELANIE (Priority 4)

### SuperGrid + AMD Model Endpoint
1. **Melanie:** Start 5 SuperNodes per `MELANIE.md`
2. **Moly:** Configure env vars:
   ```bash
   export FLWR_MODEL_API_ENDPOINT="<hackathon /v1/responses endpoint>"
   export FLWR_MODEL_API_KEY="<hackathon Slack key>"
   export VANNA_MODEL_ID="<matching model ID>"
   ```
3. **Moly:** Run local SuperLink + AgentApp:
   ```bash
   uv run flower-superlink --insecure
   # In another terminal:
   cd apps/agent
   uv run flwr run . local-superlink --stream
   ```
4. **Or:** Run directly on SuperGrid (needs Melanie's 5 nodes):
   ```bash
   cd apps/agent
   uv run flwr run . supergrid --federation @molyleela/Vanna --stream
   ```

---

## 🔗 KEY FILES (Current)

| File | Purpose |
|------|---------|
| `apps/agent/vanna_agent/agent_app.py` | **Full 6-agent orchestrator entry point** |
| `apps/agent/vanna_agent/agents/orchestrator.py` | **OrchestratorAgent sequencing all 6 agents** |
| `apps/agent/vanna_agent/agents/*.py` | 7 independent agent roles (add `explain()` here) |
| `apps/agent/vanna_agent/agents/contracts.py` | Strict Pydantic handoff schemas |
| `apps/agent/vanna_agent/domain.py` | Deterministic Vanna + LastLook + governance |
| `packages/vanna-core/src/vanna_core/` | Shared schemas, privacy, decisioning |
| `scripts/local_demo.py` | Endpoint-independent demo (works!) |
| `scripts/sync_federation_artifact.py` | Federation → Agent handoff |
| `tests/test_agent.py` | AgentApp pipeline tests (extend for Priority 3) |
| `tests/test_all_agents.py` | All 7 agents tested independently (extend for Priority 3) |
| `TECH_ARCH.md` | Architecture & integration contracts |
| `AGENTS.md` | Contribution & safety protocol |
| `HANDOVER.md` | Updated with SuperGrid connection guide |
| `MELANIE.md` | SuperNode setup guide for friend |
| `TODO.md` | This file |

---

## 📌 IMMEDIATE NEXT STEPS

**Moly:** Pick one Priority 2 task (e.g., add `explain()` to `VannaAgent`)  
**Melanie:** Follow `MELANIE.md` to start 5 SuperNodes when ready

The **local demo is fully functional** — no blocker for hackathon demo preparation.