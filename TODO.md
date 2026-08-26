# Vanna Hackathon — Completion TODO

**Last updated:** 2026-08-26 (evening)  
**Status:** ✅ **Priorities 1, 2, 4 DONE** — 6-agent chain with per-agent `explain()` contributions; **SuperGrid live end-to-end** (federation run `12309076582906127164`, AgentApp run `1896158749138907396`)  
**Remaining:** Priority 3 (tests), Priority 5 (metrics), AMD model ID (blocked on hackathon Slack), audit-gap fixes, demo rehearsal

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
| **2.1** | Add `explain()` methods to each agent for LLM narration | ✅ Done (`ddc3815`) | Low |
| **2.2** | Structured handoff payloads between agents | ✅ Done — `AgentContribution` contract (`ddc3815`) | Low |
| **2.3** | Orchestrator streams each agent's contribution | ✅ Done — contributions collected in handoff order, rendered per-agent (`ddc3815`) | Low |
| **3.1** | Timeout/retries for model calls | ⬜ Not started | Medium |
| **3.2** | Test malformed agent outputs caught | ⬜ Not started | Medium |
| **3.3** | Test child-agent failure → deterministic fallback | ⬜ Not started | Medium |
| **4.1** | AMD model ID from hackathon Slack → re-run with `--run-config "model-id='...'"` | ⏳ Blocked on Slack (run-config override ready, `b421dd2`) | Low |
| **4.2** | Start local SuperLink: `uv run flower-superlink --insecure` | ⬜ Not started (optional — SuperGrid path works) | Medium (infra) |
| **4.3** | Run AgentApp on SuperGrid `@molyleela/Vanna` | ✅ Done — run `1896158749138907396` (~22s, fallback narration) | Medium (infra) |
| **4.4** | 5 SuperNodes registered + online on SuperGrid | ✅ Done — federation run `12309076582906127164` (3 rounds, 5/5 nodes, 0 raw records) | — |
| **5.1** | Capture federation round times, loss improvement | 🟡 Partial — SuperGrid ~2.5 min measured; **eval loss rose 0.64→0.78** (retune `local-trees` before claiming improvement) | Low |
| **5.2** | Capture AgentApp latency (with/without model) | ✅ Done — ~22s SuperGrid with fallback; local demo <1s | Low |
| **5.3** | Update README demo flow with measured numbers | ⬜ Not started — README still says "FedAvg"/"until orchestrator merge" (stale) | Low |

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

**Moly:** Priority 3 tests (timeout/retry, malformed output, child-failure fallback) or README refresh (5.3)  
**Melanie:** Send the AMD model ID from hackathon Slack (only blocker for live LLM narration) — full context in `HANDOVER_MELANIE.md`

The **local demo and the SuperGrid path are both fully functional** — no blocker for hackathon demo preparation. Remaining demo prep: rehearse the `DEMO.md` script, restart/verify the 5 nodes beforehand (`flwr supernode list supergrid`).

---

## 🔎 REVIEW GAPS (skeptical audit — 2026-08-26)

Findings from a code review of what is actually wired vs. what the docs claim.
These are the real "not finished" items. Ordered by how badly they undercut the
demo narrative.

### 🔴 Critical — headline claims the code does not back up

- [ ] **Federation output is mostly hardcoded, not learned.**
  `server_app.export_approved_evidence` only takes `fill_probability` from the
  trained model (at one fixed high-vol feature vector per LP). `slippage`,
  `latency`, `displayed_price_benefit`, `rejection_asymmetry`, `sample_count`
  are a hardcoded `profiles` dict — and those constants dominate
  `domain.execution_cost`. Either derive these from the model/data, or stop
  claiming "the federated model recommends the route."
- [ ] **"Local XGBoost vs Federated" comparison is circular.**
  `xgboost_local._train_local_xgb_models` (and the duplicate in `connectors.py`)
  trains on synthetic targets built from the *same constants* the federation
  evidence hardcodes, so `model_agreement` is guaranteed. Rebuild as a genuine
  local-only vs federated comparison on a held-out set, or remove the claim.
- [ ] **Compute the actual commercial result.** PRD §5.10 / README "local vs
  federated bps improvement" is still a placeholder — nothing computes it.
- [ ] **Tests are green but cover the wrong code.** `test_federation.py` tests
  `vanna_federation.model` (dead logistic model). The real `FedXgbBagging` path
  (`xgboost_federated.py`) has zero tests. Add tests for the XGBoost train/eval,
  `run_pipeline`, orchestrator end-to-end, connectors, and model-failure fallback.

### 🟠 High — stale docs / stale "measured" numbers

- [ ] **Purge the stale metric.** HANDOVER "loss 0.6931 → 0.6646" is the old
  logistic cold-start (ln 2); the XGBoost run starts pre-trained and can't hit
  0.6931. Re-capture from a real XGBoost run or delete it (PRD requires real figures).
- [ ] **Fix contradictory docs.** README + TECH_ARCH still say "NumPy logistic
  model" and "future / not-yet-merged OrchestratorAgent"; HANDOVER/TODO say it's
  merged. Federation is XGBoost now — drop the "federated logistic" label
  everywhere (commit msg, comparison labels, docstrings).

### 🟡 Medium — architecture debt

- [ ] **`packages/vanna-core` is orphaned** — no shipping app imports it (only
  tests). Either wire the apps to it or delete it (it's a 3rd parallel copy of
  schemas/privacy/decisioning/governance).
- [ ] **Remove dead/duplicate code:** `federation/xgboost_model.py` (0 importers),
  `federation/model.py` (test-only), `domain.govern` (unused), and the duplicated
  model-comparison impl (`xgboost_local` vs `connectors`).
- [ ] **"Live connectors" are constant fallbacks in the real path.** With no
  configured connector/API key, every `_or_fallback` returns a fixed constant and
  `execution_history_or_fallback` returns the *same* values for every provider —
  so "live enrichment" is a near no-op. Make it real or stop advertising it.

### 🟢 Low

- [ ] `market_data_or_fallback` only catches `ConnectorError`; the Alpha Vantage
  path can raise `KeyError`/`httpx` errors that escape the fallback.
- [ ] `.env` listed twice in `.gitignore` (harmless; `.env` is correctly untracked).