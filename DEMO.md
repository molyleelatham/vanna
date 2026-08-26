# Vanna — Demo Guide

**One-liner:** Five competing FX desks collaboratively learn which liquidity
provider actually *executes* — without any desk ever sharing a raw order — and
a six-agent Flower chain turns that shared evidence into a governed,
human-controlled routing decision.

---

## The problem

In FX last-look markets, the tightest displayed quote is often **not** the best
executable quote. Liquidity providers (LPs) can reject trades at deal time
("last look"), and conditional rejection patterns — rejecting exactly when the
market moved against the LP — cost desks real money.

Each trading desk only sees **its own** fills and rejects. No single desk has
enough data to tell whether an LP's rejection pattern is systematic. The
obvious fix — pooling execution data across desks — is a non-starter:

- Raw orders carry client identities, account IDs, UTIs, and live intent.
- Desks are competitors; sharing order flow is commercially and legally toxic.
- Collective routing decisions between competitors raise collusion concerns.

So every desk routes on partial information, and the LP with the flashiest
displayed quote keeps winning flow it doesn't deserve.

## Features

**Federated execution intelligence**

- Five simulated desks train on private execution histories; only model
  updates ever leave a desk.
- Two federation modes: `FedXgbBagging` over XGBoost (default) and an opt-in
  FedAvg logistic model under **SecAgg+ secure aggregation**, where the server
  only ever reconstructs the masked weighted average of desk updates.
- Per-round model checkpointing, a training manifest, feature-importance
  export, and a final ensemble/evidence store under `artifacts/`.
- The federation exports exactly one typed artifact —
  `provider_evidence.json`: per-LP fill probability, rejection probability,
  expected slippage/latency, displayed-price benefit, and conditional
  rejection asymmetry, with cohort size and privacy counters attached.

**Expected-execution-value routing**

- Vanna ranks providers by expected *executable* cost —
  `P(fill) × price benefit − slippage − rejection cost − latency cost` —
  not by displayed price.
- Local XGBoost models run as a client-side benchmark against the federated
  predictions, with feature importance and a model-agreement flag.

**Six-agent collaborative chain**

- **Vanna** — execution-value ranking and route recommendation.
- **LastLookAgent** — conditional rejection-asymmetry signal; explicitly a
  review signal, never a misconduct finding.
- **CounterpartyRiskAgent** — explainable reliability score and route posture;
  never automatic exclusion.
- **MarginAgent** — margin/leverage/settlement pressure with a size
  multiplier; never auto-liquidation.
- **ManipulationWatch** — quote-pattern surveillance signal for review only.
- **GovernanceAgent** — final deterministic decision:
  `ALLOW_LOCAL_RECOMMENDATION`, `REDUCE_SIZE`, `USE_LOCAL_FALLBACK`,
  `HUMAN_REVIEW`, or `SUPPRESS_COLLECTIVE_OUTPUT`.

**Live-data connectors**

- Six typed connectors — market data, order flow, execution history, risk
  metrics, surveillance feed, federation metrics — exposed to the model as
  function tools in a bounded 3-turn loop.
- Every connector has a safe fallback; market data falls back to a direct
  Alpha Vantage call for real FX rates when Runtime connectors are
  unavailable. A hard 10-call budget per run bounds connector use.

**Safety and oversight**

- No auto-execution, no blacklists, no collective instructions, no misconduct
  findings — enforced as `Literal[False]` fields on the Pydantic contracts,
  not just promised in prose.
- Anti-collusion controls: minimum cohort size, evidence freshness window,
  synchronized-routing concentration check, rare-participant query block.
- Human review is a first-class outcome; every recommendation carries a
  reason, confidence, model version, and timestamp.

## How Flower is used

Flower is the substrate, not a decoration:

| Flower piece | How Vanna uses it |
|---|---|
| **SuperGrid** | Deployment federation `@molyleela/Vanna` runs both FAB kinds remotely; verified federation run `12309076582906127164` (3 rounds, 5/5 nodes, 0 failures, ~2.5 min) and AgentApp run `1896158749138907396` (full chain, ~22 s) |
| **SuperNodes** | 5 registered nodes, one per desk, each with EC-key node auth (`--auth-supernode-private-key`), its own runtime port, and its own staged `desk_N.npz` partition — setup fully scripted (`supernode_setup.sh`, `start_supernode_desk_*.sh`) |
| **SuperExec** | Runs the short-lived workloads: the `ServerApp`/`ClientApp` pair for federation and the `AgentApp` for the agent chain, as isolated processes on the SuperLink/SuperNode substrate |
| **ServerApp + ClientApp FAB** (`vanna-federation`) | `FedXgbBagging` strategy with per-round checkpointing, or opt-in `SecAggPlusWorkflow` (FedAvg logistic, `num-shares=5`, `reconstruction-threshold=3`); exports the approved evidence artifact |
| **AgentApp FAB** (`vanna-agent`) | The 6-agent chain as a Flower Agent: `AgentSession`, streamed model events via `agent.events.emit`, run-config order input (`agent.input`), compact state persisted in Flower `Context` under a lock |
| **Connectors** | `agent.connectors.call()` wrapped in a typed, rate-limited `ConnectorClient`; six function tools in the model loop; structured `ConnectorError` with fallbacks instead of crashes |
| **Simulation runtime** | Same FABs run locally (`num-supernodes=5`) for development and as the zero-network demo fallback |

A Flower FAB cannot combine an `AgentApp` with a `ServerApp`/`ClientApp` pair,
so the repo is deliberately two FABs joined by one typed artifact. That
artifact *is* the collaboration boundary.

## Privacy and federation

The privacy boundary is structural — enforced in code at three layers:

1. **Nothing raw leaves the desk.** ClientApps return only model bytes and
   numeric metrics; `validate_shared_payload` asserts no prohibited field
   (`client_id`, `account_id`, `real_order_id`, `uti`, `exact_notional`,
   `exact_timestamp`, `position`, `live_intention`) before anything is sent.
   The exported artifact carries `raw_records_shared: 0` and
   `client_identities_shared: 0` as measured counters.
2. **Pseudonymization, honestly labelled.** Shared analytics use
   `HMAC(desk_secret, local_order_id)` pseudonyms and bucketed features (size,
   latency, volatility, slippage). The mapping to real order IDs, UTIs, and
   client records stays in the local desk vault. This is pseudonymization,
   not anonymization — and the docs say so.
3. **The AgentApp re-validates.** `load_evidence` recursively scans the
   evidence artifact for prohibited fields before any agent can read it.

With `secure-aggregation=true`, individual desk updates are never visible to
the server at all: SecAgg+ reconstructs only the weighted average, and
per-round checkpoints contain the aggregate by construction. (SecAgg+ is a
summation protocol and cannot merge XGBoost trees, so this mode uses the
transparent logistic model — whose weights double as feature attribution.)

Federation is a **background** model-update path. Live routing uses the
locally cached model and never blocks on SuperGrid.

## The tracks

**Track 1 — SuperGrid: collaboration multiplies agent value.** No single
desk's agents can see the market-wide pattern; five desks' agents can. The
demo makes the multiplication visible: a local-only recommendation is
low-confidence and wrong-footed by LP_A's tight displayed quote, while the
federated evidence lets the same agent chain route to LP_B at 2.03 bps
expected executable cost. Each agent in the chain contributes something the
others cannot — cost ranking, rejection asymmetry, reliability, margin,
surveillance, governance — and every contribution is rendered as its own
visible line in the output.

**Track 2 — Infrastructure: a reusable collaboration layer.** The FX agents
are the proof case; the product is the infrastructure: privacy-controlled
feature transformation, federated training with optional secure aggregation,
typed evidence exchange, explicit context management, latency-aware local
inference, governance and anti-collusion controls, contribution scoring, and
graceful failure at every layer. The same layer transfers to cross-bank fraud
detection, insurance collaboration, or trade surveillance without redesign.

## Why technical excellence

- **Verified end-to-end on real infrastructure, today.** SuperGrid federation
  run `12309076582906127164` — 3 rounds, 5/5 nodes, 0 failures, 0 raw records
  shared, ~2.5 min. SuperGrid AgentApp run `1896158749138907396` — full
  six-agent chain, LP_B @ 2.03 bps, Governance HUMAN_REVIEW, ~22 s. Local
  simulation: 3 rounds in 12.81 s, centralised eval loss 0.6931 → 0.6646.
- **Determinism where it matters.** Every number in a recommendation comes
  from typed, tested code. The LLM narrates the chain through a streamed,
  bounded tool loop (Responses API, `MAX_TOOL_TURNS=3`); it never decides.
  If the endpoint fails, a deterministic fallback renders the same answer.
- **Safety encoded in the type system.** `automatic_execution: Literal[False]`,
  `automatic_blacklist: Literal[False]`, `collective_instruction:
  Literal[False]`, `misconduct_finding: Literal[False]` — unsafe outputs are
  unrepresentable, not just discouraged. All contracts are `extra="forbid"`.
- **Every layer degrades gracefully.** No model endpoint → deterministic
  narration. No connector → typed fallback values. Failed agent → fallback
  answer. No SuperGrid → local simulation. Stale evidence or small cohort →
  `USE_LOCAL_FALLBACK`. The demo cannot be bricked by one outage.
- **Tested, not just asserted.** 21 passing tests cover privacy boundaries,
  federation behaviour, routing, governance, and every agent role. Both FABs
  build cleanly with pinned Flower `1.35.0`.
- **Engineering for audit.** Training manifests, per-round checkpoints,
  model digests, feature-importance exports, and a persisted live-data
  snapshot mean every demo claim traces to an artifact on disk.

## Demo script (3–5 minutes)

1. **(30s) Problem:** LP_A shows the tightest quote. Should the desk take it?
   No single desk has enough data to know.
2. **(45s) Federation:** show 5 online SuperNodes
   (`flwr supernode list supergrid`), then the completed federation run —
   point at `raw-records-shared: 0` and the 5/5 node sampling each round.
3. **(60s) Agent chain:** run the AgentApp (or local demo) and walk the six
   contribution lines — each agent visibly adds something the others can't:
   cost ranking, rejection asymmetry, reliability, margin, surveillance,
   governance.
4. **(45s) The twist:** LP_B wins on *executable* cost despite LP_A's tighter
   displayed quote; LastLook flags LP_A's asymmetry as review-only.
5. **(30s) Governance:** HUMAN_REVIEW outcome — independent controls triggered;
   no automation overreach.
6. **(30s) Resilience:** point out the fallback line — model narration failed
   on the live run and the answer still rendered deterministically.

### Commands

```bash
# Live SuperGrid path (nodes must be online: flwr supernode list supergrid)
cd apps/federation && uv run flwr run . supergrid --federation @molyleela/Vanna --stream

# Optional: federation with SecAgg+ secure aggregation (logistic model)
cd apps/federation && uv run flwr run . --federation-config="num-supernodes=5" \
  --run-config "secure-aggregation=true" --stream

# AgentApp on SuperGrid
cd ../agent && uv run flwr run . supergrid --federation @molyleela/Vanna --stream \
  --run-config "agent.input='{\"pair\":\"EUR/USD\",\"side\":\"BUY\",\"size_bucket\":\"1m-5m\",\"volatility\":\"high\",\"available_providers\":[\"LP_A\",\"LP_B\",\"LP_C\"]}'"

# Zero-network fallback (always works)
uv run python scripts/local_demo.py
```

### Trading terminal demo

```bash
# Optional: enables a public quote in the terminal; never commit this key.
export ALPHAVANTAGE_API_KEY="<key>"

# Terminal 1
cd apps/agent && uv run python -m vanna_agent.gateway

# Terminal 2
cd apps/dashboard && npm install && npm run dev
```

Enter only the bucketed EUR/USD ticket fields and select **Assess order**.
The terminal displays the governed local decision and the separate Flower
runtime state. **Send to approval queue** creates a local
`PENDING_HUMAN_APPROVAL` audit record; it does not create, transmit, or execute
a broker/OMS order.

## Honest limitations (say these if asked)

- Desk data is synthetic; it demonstrates the mechanism, not market truth.
- In the latest SuperGrid run, held-out eval loss rose across rounds with
  `local-trees=1` — the pipeline works, the hyperparameters need tuning before
  claiming model improvement.
- Part of the evidence artifact is derived from desk profile parameters, not
  purely from the trained model.
- `flwr pull` is unsupported on SuperGrid, so run artifacts stay server-side;
  the agent demo consumes the locally generated equivalent.
- Secure aggregation is implemented as an opt-in mode (SecAgg+ over the
  logistic model); the default XGBoost path aggregates tree ensembles in the
  clear to the server. There is no differential privacy. Vanna is advisory
  and executes nothing.
