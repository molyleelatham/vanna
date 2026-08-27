# Vanna — Cambridge Collaborative Agent Hackathon 2026

**Five competing FX desks learn which liquidity provider actually *executes* —
without any desk sharing a single raw order — and a six-agent Flower chain
turns that shared intelligence into a governed, human-controlled decision.**

---

## Outline

1. The problem: displayed price ≠ executable price
2. The mechanism: federate the evidence, then let agents reason over it
3. Data science & AI: what's learned, what's compared, what's narrated
4. Federation: the privacy architecture that makes collaboration legal
5. Impressive tackles: the hard engineering problems solved
6. Measured results
7. Track mapping

---

## 1. The problem

In FX last-look markets, a liquidity provider can show a beautiful quote and
then **reject the trade at deal time**. The tightest displayed price is
routinely the worst executable price.

Every desk sees only its own fills and rejects — too little data to prove an
LP's rejection pattern is systematic. Pooling order data across competitor
desks is legally and commercially impossible (client identities, UTIs, live
intent, collusion risk). So desks keep overpaying the flashiest LP.

**Vanna's answer:** move the *model*, not the data.

## 2. How it tackles the problem

```text
5 desks train locally on private execution histories
        │  only model updates cross the wire
        ▼
Flower federation (SuperGrid) → one approved evidence artifact
        │  schema-validated, provenance-labelled, 0 raw records
        ▼
Six typed agents in a strict handoff chain
        │  Vanna → LastLook → CounterpartyRisk → Margin → ManipulationWatch → Governance
        ▼
A governed, advisory decision a human approves
```

The moment that lands with judges: **LP_A shows the best displayed quote
(+0.45 bps) and the worst executable cost (~6.0 bps). The federation routes
to LP_B at ~2.1 bps — and LastLook flags LP_A's rejection asymmetry as a
review signal, not an accusation.**

## 3. Data science & AI

- **Federated XGBoost (FedXgbBagging):** each desk boosts the shared ensemble
  with locally trained trees; the server merges boosters per round. Nonlinear
  LP × volatility interactions are the real signal — linear models miss them.
- **Regression-derived evidence:** slippage, latency, and rejection
  probability come from XGBoost regression models per target, not hand-set
  constants; fill probability comes from the federated ensemble itself.
- **Genuine generalization test:** a model trained on *one desk alone* is
  scored against the *five-desk federated ensemble* on held-out data, per
  provider. This is the measured value of collaboration (see results).
- **Feature importance exported** from the ensemble — the model explains
  which signals drive fills (LP_A × high volatility dominates).
- **LLM as narrator, never decider:** Qwen3.5-397B (AMD endpoint, Responses
  API) streams a structured write-up of the finished chain through a bounded
  6-tool loop with a 120 s timeout. Every number comes from deterministic,
  tested code. Endpoint failure → deterministic fallback renders the same
  answer.
- **Strict typed contracts everywhere:** Pydantic `extra="forbid"` schemas
  for orders, evidence, and every agent assessment; malformed outputs are
  unrepresentable.

## 4. Federation

- **Real SuperGrid deployment:** five registered SuperNodes (EC P-384 key
  auth), one per desk, on the `@molyleela/Vanna` deployment federation —
  not a laptop-only simulation.
- **Privacy enforced in code at three layers:** ClientApps return only model
  bytes + metrics; `validate_shared_payload` rejects prohibited fields before
  anything is sent; the AgentApp re-validates the artifact before any agent
  reads it. Measured counters: `raw_records_shared: 0`,
  `client_identities_shared: 0`.
- **Optional SecAgg+ mode:** one run-config flag (`secure-aggregation=true`)
  switches to masked aggregation — the server reconstructs only the weighted
  average of desk updates, never an individual update. (Summation protocols
  can't merge XGBoost trees, so this mode uses the transparent logistic
  model — the trade-off is documented, not hidden.)
- **Anti-collusion controls:** minimum cohort of 5, evidence freshness
  window, synchronized-routing concentration check, rare-participant query
  block. Governance can suppress collective output entirely.

## 5. Impressive tackles

- **First-day Flower 1.35.0 SuperGrid deployment:** node registration via
  SSH-format EC keys, Fleet API endpoint discovery, per-node runtime ports,
  and runtime dependency installation — distilled into five one-command
  scripts (`start_supernode_desk_*.sh`).
- **Bridged SecAgg+ into the new Message API:** a conditional client mod
  applies `secaggplus_mod` only to SecAgg handshake traffic and lets
  FedXgbBagging messages pass through — both modes share one ClientApp.
- **Found and fixed a silent failure mode:** the chat-completions tool schema
  was being rejected by the Responses-compatible AMD endpoints, silently
  forcing fallback on every run. Flat Responses-schema tools + honest
  availability flags fixed it — and made the failure mode loud instead of
  silent.
- **Killed a data-honesty bug:** connector fallback constants were being
  *blended into assessments*, flattening inter-provider differences. Agents
  now blend only genuinely live data; tools report `"available": false`.
- **Safety in the type system:** `automatic_execution`,
  `automatic_blacklist`, `collective_instruction`, `misconduct_finding` are
  `Literal[False]` — unsafe outputs fail schema validation, not just policy.
- **Graceful degradation at every layer:** no model → deterministic
  narration; no connector → static evidence; failed agent → safe
  human-review answer; no SuperGrid → local simulation. The demo cannot be
  bricked by one outage.
- **Human-in-the-loop as infrastructure:** a local gateway + dashboard turns
  governed decisions into non-executable `PENDING_HUMAN_APPROVAL` audit
  records — never a broker order.

## 6. Measured results (all from real runs, 26 Aug 2026)

| Claim | Evidence |
|---|---|
| Federation on SuperGrid | Run `12309076582906127164`: 3 rounds, 5/5 nodes, 0 failures, 0 raw records, ~2.5 min |
| AgentApp on SuperGrid | Runs `1896158749138907396`, `17460595724030593185`: full chain, ~22 s |
| Live Qwen narration | Local SuperLink runs (~65 s), full six-agent markdown |
| SecAgg+ secure mode | Simulation: 3 rounds, 5/5 nodes, 16.4 s, loss 0.6931 → 0.6528 |
| **Collaboration reverses conclusions** | Desk 0 alone: LP_C fills **~60%**. Five desks federated: **~11%**. Held-out loss on LP_B: 0.50 federated vs 0.62 single-desk |
| Test coverage | 46 passing — privacy, both federation modes, all agents, fallback paths, gateway |

## 7. Track mapping

- **Track 1 (SuperGrid):** collaboration visibly multiplies agent value — a
  six-agent chain where every contribution renders as its own line, on
  evidence no single desk could produce, on real SuperGrid infrastructure.
- **Track 2 (Infrastructure):** a reusable collaboration layer — typed
  evidence exchange between FABs, conditional SecAgg+ bridging, AMD endpoint
  integration, approval-gateway governance — proven on a concrete,
  explainable use case.

**The one-liner:** six agents that each see one risk dimension produce a
governed decision none could make alone — on data no desk was willing to
share.
