# Vanna Hackathon — Completion TODO

**Last updated:** 2026-08-26  
**Status:** Federation + Agent FABs build & run; 13 tests pass; local demo works  
**Blocker:** AgentApp only runs 2 of 6 agents (Vanna → LastLook); GovernanceAgent not wired

---

## ✅ COMPLETE

| Component | Verification |
|-----------|--------------|
| Federation FAB (5 desks, FedAvg, 3 rounds) | `uv run flwr run . --federation-config="num-supernodes=5" --stream` ✓ |
| Agent FAB (6 typed agent roles) | `uv run flwr build` ✓ |
| Core domain: schemas, privacy, deterministic decisioning | `uv run pytest -q` (13 passed) ✓ |
| Local deterministic demo (no federation/model needed) | `uv run python scripts/local_demo.py` ✓ |
| Artifact sync (federation → agent) | `uv run python scripts/sync_federation_artifact.py` ✓ |
| Safety invariants enforced | Privacy checks, no auto-execution/blacklist ✓ |

---

## ⚠️ HALF-FINISHED / GAPS

| # | Gap | Impact | Effort |
|---|-----|--------|--------|
| 1 | **Only 2-agent chain active** (Vanna→LastLook); CounterpartyRisk, Margin, ManipulationWatch, Governance defined but not called in AgentApp | GovernanceAgent never runs → final demo output missing | Medium |
| 2 | **No OrchestratorAgent** to sequence all 6 agents and build GovernanceContext | Required for full agent chain | Medium |
| 3 | **Model endpoint not configured** — AgentApp falls back to deterministic (works but no LLM narration) | Low (config) |
| 4 | **SuperGrid end-to-end not run** — needs credentials + AMD model endpoint | Medium (infra) |
| 5 | **Missing integration tests**: timeout, malformed-output, child-failure fallback | HANDOVER.md item #4 | Medium |
| 6 | **LLM prompts not refined** for all 6 agents | HANDOVER.md item #1 | Low |
| 7 | **Demo metrics not recorded** — only measured numbers allowed in demo | HANDOVER.md item #5 | Low |
| 8 | **Orchestrator merge pending** — architectural, after interfaces stable | HANDOVER.md | High |

---

## 🎯 CRITICAL PATH FOR 3-5 MIN DEMO

The demo flow (README) expects step 7: *"Show the governance result, human control, and deterministic fallback"* — **GovernanceAgent not wired**.

### Minimal Fix: OrchestratorAgent (~60 lines)
Create `apps/agent/vanna_agent/agents/orchestrator.py` that:
1. `VannaAgent.assess()` → `Recommendation`
2. `LastLookAgent.assess()` → `LastLookAssessment`
3. `CounterpartyRiskAgent.assess()` → `CounterpartyRiskAssessment`
4. `MarginAgent.assess(MarginContext)` → `MarginAssessment`
5. `ManipulationWatch.assess(MarketPatternContext)` → `ManipulationAssessment`
6. `GovernanceAgent.assess(GovernanceContext)` → `GovernanceAssessment` (final decision)
7. Stream each agent's narration (LLM or deterministic fallback)

Then update `agent_app.py` to call orchestrator instead of 2-agent chain.

---

## 📋 PRIORITIZED WORK PLAN

### Priority 1: Wire All 6 Agents Into AgentApp (Critical Path)
| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Create `OrchestratorAgent` class sequencing all 6 agents | `apps/agent/vanna_agent/agents/orchestrator.py` (new) |
| 1.2 | Update `agent_app.py` to call orchestrator | `apps/agent/vanna_agent/agent_app.py` |
| 1.3 | Construct `MarginContext` / `MarketPatternContext` from order + evidence | `apps/agent/vanna_agent/agent_app.py` |
| 1.4 | Preserve deterministic fallback on any agent/model failure | `apps/agent/vanna_agent/agent_app.py` |

### Priority 2: Refine LLM Prompts for All Agents (Demo Polish)
| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Add `explain()` methods to each agent for LLM narration | `apps/agent/vanna_agent/agents/*.py` |
| 2.2 | Create structured handoff payloads between agents | `apps/agent/vanna_agent/agents/contracts.py` (extend) |
| 2.3 | Update orchestrator to stream each agent's contribution | `apps/agent/vanna_agent/agents/orchestrator.py` |

### Priority 3: Integration Tests & Failure Handling (Reliability)
| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Add timeout/retries for model calls | `apps/agent/vanna_agent/agent_app.py` |
| 3.2 | Test malformed agent outputs are caught | `tests/test_all_agents.py` (extend) |
| 3.3 | Test child-agent failure triggers deterministic fallback | `tests/test_agent.py` (extend) |

### Priority 4: SuperGrid End-to-End Run (Track 1)
| Task | Description |
|------|-------------|
| 4.1 | Configure `FLWR_MODEL_API_ENDPOINT`, `FLWR_MODEL_API_KEY`, `VANNA_MODEL_ID` |
| 4.2 | Start local SuperLink: `uv run flower-superlink --insecure` |
| 4.3 | Run AgentApp: `uv run flwr run . supergrid --federation @molyleela/Vanna --stream` |

### Priority 5: Record Measured Demo Metrics (Delivery)
| Task | Description |
|------|-------------|
| 5.1 | Capture federation round times, loss improvement |
| 5.2 | Capture AgentApp latency (with/without model) |
| 5.3 | Update README demo flow with measured numbers |

---

## 👥 RECOMMENDED WORKSTREAM SPLIT (per AGENTS.md)

| Workstream | Scope |
|------------|-------|
| **Orchestrator + AgentApp wiring** (Primary) | Tasks 1.1–1.4, 2.1–2.3 |
| **Tests + failure handling** (Secondary) | Tasks 3.1–3.3 |
| **SuperGrid run + metrics** (Secondary) | Tasks 4.1–4.3, 5.1–5.3 |

---

## 🚀 QUICK WINS (Can Do Today)

1. **Add OrchestratorAgent** — ~60 lines, wires existing tested agents
2. **Update agent_app.py** — Replace 2-agent chain with orchestrator call
3. **Run local demo again** — Now shows full governance output
4. **Add 2 integration tests** — Timeout + malformed output

---

## 📝 HANDOVER NOTES (from HANDOVER.md)

> **Remaining work:**
> 1. Refine prompts/model-backed explanations for completed deterministic agent roles
> 2. Merge orchestration layer after agent/infrastructure interfaces stable
> 3. Run complete AgentApp on `@molyleela/Vanna` with AMD model
> 4. Add agent timeout, malformed-output, child-failure integration tests
> 5. Record only measured final demo metrics

> **Known limitations:**
> - Synthetic dataset ≠ production market behavior
> - Simulation ≠ production privacy/security/latency proof
> - Model updates can leak info without secure aggregation/DP
> - Last-look signal ≠ misconduct proof
> - Vanna is advisory — no auto-execution, no coordination

---

## 🔗 KEY FILES

| File | Purpose |
|------|---------|
| `apps/agent/vanna_agent/agent_app.py` | Current bounded 2-agent entry point |
| `apps/agent/vanna_agent/agents/` | 6 independent agent roles |
| `apps/agent/vanna_agent/agents/contracts.py` | Strict Pydantic handoff schemas |
| `apps/agent/vanna_agent/domain.py` | Deterministic Vanna + LastLook + governance |
| `packages/vanna-core/src/vanna_core/` | Shared schemas, privacy, decisioning |
| `scripts/local_demo.py` | Endpoint-independent demo |
| `scripts/sync_federation_artifact.py` | Federation → Agent handoff |
| `tests/test_all_agents.py` | All 6 agents tested independently |
| `TECH_ARCH.md` | Architecture & integration contracts |
| `AGENTS.md` | Contribution & safety protocol |

---

## 📌 NEXT ACTION

**Start Priority 1.1:** Create `OrchestratorAgent` in `apps/agent/vanna_agent/agents/orchestrator.py`

This unblocks the full demo by enabling GovernanceAgent to produce the final decision that step 7 of the demo flow requires.