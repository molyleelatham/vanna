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
- A genuine **one-desk vs five-desk comparison**: a model trained on desk 0's
  partition alone is scored against the federated final ensemble on held-out
  data, per provider. This is the measured proof that collaboration changes
  conclusions — not a restatement of the constants the evidence came from.

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
- Honest availability: agents blend connector data into assessments **only
  when it is genuinely live** (`*_if_live` returns `None` otherwise); tool
  answers report `"available": false` instead of silently returning constants.
  Market data falls back to a direct Alpha Vantage call for real FX rates.
  A hard 10-call budget per run bounds connector use.

**Safety and oversight**

- No auto-execution, no blacklists, no collective instructions, no misconduct
  findings — enforced as `Literal[False]` fields on the Pydantic contracts,
  not just promised in prose.
- Anti-collusion controls: minimum cohort size, evidence freshness window,
  synchronized-routing concentration check, rare-participant query block.
- Human review is a first-class outcome; every recommendation carries a
  reason, confidence, model version, and timestamp.
- Every exported evidence field carries a **provenance label** (federated
  prediction vs synthetic profile constant) — no ambiguity about what the
  model learned.

**LLM narration via AMD endpoint**

- Qwen3.5-397B (hackathon AMD endpoint, Responses API) narrates the finished
  chain through a streamed, bounded tool loop with a 120 s timeout. The model
  explains; it never decides. Endpoint failure degrades to a deterministic
  fallback rendering of the same typed assessments.

**Approval gateway and dashboard**

- A local-only gateway (`vanna_agent.gateway`) runs the AgentApp via the local
  SuperLink and exposes the governed decision to a Vite/TS dashboard
  (`localhost:5173`). "Send to approval queue" creates a local, non-executable
  `PENDING_HUMAN_APPROVAL` audit record — never a broker/OMS order.

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

## Why Flower was necessary — drilled into the architecture

Every hard requirement maps to a Flower primitive that would be a project in
itself to rebuild:

1. **"Train on data that can't move" → deployment runtime.** The ClientApp
   executes *on the desk's machine* (SuperNode); only serialized model bytes
   travel. Compute goes to the data because the data can never leave.
2. **"Five competitors, one shared model" → federation + strategy.**
   SuperLink coordinates, `FedXgbBagging` runs the aggregation loop, and
   federation membership (`register` + `add-supernode`) is the trust
   boundary — only registered keys can join a round.
3. **"Prove the nodes are who they say" → EC-key node auth.** Each SuperNode
   authenticates with its registered P-384 key, so a malicious "desk" cannot
   inject poisoned updates.
4. **"The agent chain is a managed workload" → AgentApp + SuperExec.**
   `Context` state persisted under lock (audit), `run-config` order input,
   `agent.events.emit` streaming to the UI, rate-limited typed connector
   calls, and an isolated `uv sync`'d runtime per run.
5. **"FL and agents can't live in one bundle" → the FAB boundary.** Flower
   forbids combining the two app kinds in one FAB — a constraint that forced
   the cleanest decision in the repo: two FABs joined by one typed,
   privacy-validated artifact.
6. **"The server shouldn't see individual updates" → SecAgg+.** Masked
   summation with key exchange, share splitting, and reconstruction
   thresholds — audited cryptography, not home-grown crypto.
7. **"The demo must survive failure" → simulation runtime + run lifecycle.**
   The same FABs run locally (`num-supernodes=5`) with zero infrastructure,
   and every run has an ID, streamed logs, and status for verification.

**The counterfactual:** without Flower, Vanna is a message queue, an auth
system, a job orchestrator, a secure-aggregation protocol, a packaging format,
and an agent runtime — six infrastructure projects before the first agent
exists. With Flower, the hackathon hours went into the part that is actually
novel: the collaboration boundary and the governed agent chain.

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
multiplication is measured, not asserted: a model trained on desk 0 alone
concludes LP_C fills **~60%** of orders, while the five-desk federated
ensemble knows it is **~11%** — collaboration literally reverses a desk's
conclusion. The same chain then routes to LP_B at 2.03 bps expected
executable cost, past LP_A's tighter displayed quote. Each agent contributes
something the others cannot — cost ranking, rejection asymmetry, reliability,
margin, surveillance, governance — and every contribution is rendered as its
own visible line in the output. All of it runs on the real
`@molyleela/Vanna` deployment federation: five authenticated SuperNodes,
completed federation and AgentApp runs.

**Track 2 — Infrastructure: a reusable collaboration layer.** The FX agents
are the proof case; the product is the infrastructure: privacy-controlled
feature transformation, federated training with optional secure aggregation,
typed evidence exchange, explicit context management, latency-aware local
inference, governance and anti-collusion controls, contribution scoring, and
graceful failure at every layer. The same layer transfers to cross-bank fraud
detection, insurance collaboration, or trade surveillance without redesign.

## Why — the questions judges ask

**Why not just pool the data?**
Raw orders carry client identities, UTIs, and live intent; desks are
competitors. Pooling is legally and commercially impossible — which is
exactly why the problem is unsolved today. Federation is the only version of
this collaboration that can exist.

**Why six agents instead of one big prompt?**
Each agent owns one regulatory-grade concern with its own typed contract:
execution value, last-look asymmetry, counterparty reliability, margin
pressure, surveillance, governance. Separation makes each one independently
testable, independently replaceable, and — critically for the demo — makes
the *value of each contribution visible*. One monolithic agent would be an
unauditable black box.

**Why does the LLM never decide?**
Numbers come from deterministic, tested code; the model only narrates
finished assessments. A model that decides is ungovernable; a model that
explains is an interface. If the endpoint dies mid-demo, the deterministic
fallback renders the same answer — resilience is the feature.

**Why XGBoost by default, and why offer SecAgg+?**
XGBoost bagging captures the nonlinear desk behavior (LP × volatility
interactions drive the signal). SecAgg+ is a summation protocol that cannot
merge trees, so the secure mode runs the transparent logistic model — the
trade-off is stated openly, and both modes export the identical evidence
schema.

**Why does governance say no so often?**
Because the controls are independent: last-look review, low confidence, stale
evidence, small cohorts, and margin pressure each escalate on their own. The
system can say yes (Clean Allow scenario) — which is what makes its "no"
credible.

**Why the approval queue instead of execution?**
Vanna is advisory by design. The gateway's `PENDING_HUMAN_APPROVAL` record is
the consequential action boundary: a human always holds the final step, and
nothing in the codebase can create, transmit, or execute a real order.

## Why technical excellence

- **Verified end-to-end on real infrastructure, today.** SuperGrid federation
  run `12309076582906127164` — 3 rounds, 5/5 nodes, 0 failures, 0 raw records
  shared, ~2.5 min. SuperGrid AgentApp run `1896158749138907396` — full
  six-agent chain, LP_B @ 2.03 bps, Governance HUMAN_REVIEW, ~22 s. SecAgg+
  secure-mode simulation: 3 rounds, 5/5 nodes, 16.4 s, centralised loss
  0.6931 → 0.6528. Qwen-narrated local SuperLink runs: ~65 s.
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
- **Tested, not just asserted.** 44 passing tests cover privacy boundaries,
  both federation modes, routing, governance, every agent role, the
  SecAgg+ contract, the gateway, and the failure fallbacks. Both FABs build
  cleanly with pinned Flower `1.35.0`.
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
6. **(30s) Resilience:** the Qwen narration is live — then point out that if
   the endpoint dies, the deterministic fallback renders the same answer
   (shown in the earlier SuperGrid run, where narration fell back cleanly).

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

# AgentApp narrated live by Qwen3.5-397B (local SuperLink with AMD endpoint running)
cd apps/agent && uv run flwr run . local-superlink --stream \
  --run-config "agent.input='{\"pair\":\"EUR/USD\",\"side\":\"BUY\",\"size_bucket\":\"1m-5m\",\"volatility\":\"high\",\"available_providers\":[\"LP_A\",\"LP_B\",\"LP_C\"]}' model-id='/models/Qwen3.5-397B-A17B-FP8'"

# Zero-network fallback (always works)
uv run python scripts/local_demo.py
```

### Trading terminal demo

```bash
# Terminal 0: local SuperLink must already be running with the model endpoint.
export FLWR_MODEL_API_ENDPOINT="<full /v1/responses endpoint>"
uv run flower-superlink --insecure

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

## Terminal scenario appendix

The terminal presets use these verified local-SuperLink inputs. Each runs the
same six-agent Flower AgentApp chain narrated by Qwen.

| Preset | Order input | Expected governed outcome |
|---|---|---|
| **The Twist** | `EUR/USD`, BUY, `1m-5m`, high, LP_A/LP_B/LP_C | LP_B at ~2.1 bps; LP_A's +0.45 bps displayed benefit loses to ~6.0 bps executable cost; `HUMAN_REVIEW`. |
| **Clean Allow** | `EUR/USD`, BUY, `<1m`, calm, LP_B | `ALLOW_LOCAL_RECOMMENDATION`. |
| **Throttle** | `EUR/USD`, BUY, `1m-5m`, normal, LP_B/LP_C | `REDUCE_SIZE`; the margin control recommends a 0.75 multiplier. |
| **Stress Escalation** | `GBP/JPY`, SELL, `>10m`, high, LP_A/LP_B/LP_C | `HUMAN_REVIEW` under stressed margin and LP_A review signals. |
| **Trust Check** | `EUR/USD`, SELL, `5m-10m`, normal, LP_A | `HUMAN_REVIEW`; LP_A is not automatically approved even when it is the only option. |

For the collaboration proof, the genuine model-comparison narration shows desk
0 estimating LP_C at roughly 60% fill probability while the five-desk
federation estimates roughly 11%. Last-look asymmetry remains a review signal,
never a misconduct finding.

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
