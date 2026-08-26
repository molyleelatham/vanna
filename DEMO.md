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

## What Vanna does

1. **Five desks train locally** on their private execution histories
   (XGBoost). Only model updates leave the desk.
2. **Flower aggregates** the updates on SuperGrid and exports one *approved
   aggregate evidence* artifact: per-LP fill probability, rejection, slippage,
   latency — with **0 raw records and 0 client identities** (enforced by
   schema validation and privacy tests, not just promises).
3. **Six typed agents** consume that evidence in a strict handoff chain:
   - **Vanna** — ranks LPs by expected *executable* cost (not displayed price)
   - **LastLookAgent** — flags conditional rejection asymmetry as a *review
     signal*, explicitly not a misconduct finding
   - **CounterpartyRiskAgent** — reliability scoring; advisory, never an
     automatic exclusion
   - **MarginAgent** — margin/settlement pressure; never auto-liquidation
   - **ManipulationWatch** — market-pattern surveillance signal only
   - **GovernanceAgent** — final deterministic decision: allow, reduce size,
     local fallback, human review, or suppress collective output
4. An LLM (when an endpoint is available) **narrates** the chain — it never
   makes the decision. If the model fails, a deterministic fallback renders
   the same answer from the typed assessments.

## Why it's good at it

- **Collaboration without data sharing.** The privacy boundary is structural:
  desks physically cannot leak raw orders because only model updates cross the
  wire, and the exported artifact is validated against a forbidden-field list
  before any agent can read it.
- **Decisions stay deterministic and local.** Numbers come from typed,
  tested code. Models explain; they don't decide. Live routing never blocks on
  a network call.
- **Every layer degrades gracefully.** No model endpoint → deterministic
  narration. No connector → static evidence. Failed agent → fallback answer.
  No SuperGrid → local simulation. The demo cannot be bricked by one outage.
- **Each agent is independently testable** against strict Pydantic contracts —
  21 tests cover routing, privacy, governance, and every agent role.

## How Flower architecture is used

Flower is the substrate, not a decoration:

| Flower piece | How Vanna uses it |
|---|---|
| **SuperGrid deployment federation** | `@molyleela/Vanna` — 5 registered SuperNodes with EC-key node auth, one per desk |
| **ServerApp + ClientApp FAB** (`vanna-federation`) | `FedXgbBagging` strategy, 3 rounds, per-round checkpointing, training manifest, approved-evidence export |
| **AgentApp FAB** (`vanna-agent`) | The 6-agent chain as a Flower Agent: `AgentSession`, 6-function tool loop, streamed model events, run-config order input |
| **Simulation runtime** | Same FABs run locally (`num-supernodes=5`) for development and as the demo fallback |
| **SuperNode deployment mechanics** | SSH-format EC keys, `flwr supernode register`, per-node runtime ports, runtime dependency installation — all scripted and documented |

A Flower FAB cannot combine an `AgentApp` with a `ServerApp`/`ClientApp` pair,
so the repo is deliberately two FABs joined by one typed artifact:
`provider_evidence.json`. That artifact *is* the collaboration boundary.

## Against the judging criteria

- **Impact.** Best-execution under last-look is a real, expensive problem for
  every FX desk, and the value proposition is one sentence: *desks learn from
  each other's outcomes without ever seeing each other's orders.* The demo
  shows a concrete case: LP_A shows the tightest quote, but the federated
  evidence routes to LP_B at 2.03 bps expected executable cost.
- **Innovation.** The novel part is the composition: federated evidence →
  typed multi-agent chain → deterministic governance. Agents don't just chat;
  each owns a distinct regulatory-grade concern, and their handoffs are strict
  contracts with privacy invariants enforced in code.
- **Use of Flower.** SuperGrid runs the real thing: 5 authenticated SuperNodes,
  a deployment federation, and both FAB kinds (ServerApp/ClientApp and
  AgentApp) exercised on SuperGrid infrastructure — plus the simulation
  runtime for the offline path.
- **Technical execution.** Verified today end-to-end: SuperGrid federation run
  `12309076582906127164` (3 rounds, 5/5 nodes, 0 failures, 0 raw records
  shared, ~2.5 min); SuperGrid AgentApp run `1896158749138907396` (~22 s, full
  chain, HUMAN_REVIEW decision); 21 passing tests; both FABs build cleanly.
- **Demo and delivery.** 3–5 minute script below; every step has a rehearsed
  fallback; the deterministic path works with zero network.
- **Safety and oversight.** No auto-execution, no blacklists, no collective
  instructions, no misconduct findings — these aren't documentation claims,
  they're `Literal[False]` fields on the contracts. Governance can suppress
  collective output entirely. Last-look asymmetry is always framed as a review
  signal.

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
cd ../agent && uv run flwr run . supergrid --federation @molyleela/Vanna --stream \
  --run-config "agent.input='{\"pair\":\"EUR/USD\",\"side\":\"BUY\",\"size_bucket\":\"1m-5m\",\"volatility\":\"high\",\"available_providers\":[\"LP_A\",\"LP_B\",\"LP_C\"]}'"

# Zero-network fallback (always works)
uv run python scripts/local_demo.py
```

## Honest limitations (say these if asked)

- Desk data is synthetic; it demonstrates the mechanism, not market truth.
- In the latest SuperGrid run, held-out eval loss rose across rounds with
  `local-trees=1` — the pipeline works, the hyperparameters need tuning before
  claiming model improvement.
- Part of the evidence artifact is derived from desk profile parameters, not
  purely from the trained model.
- `flwr pull` is unsupported on SuperGrid, so run artifacts stay server-side;
  the agent demo consumes the locally generated equivalent.
- Simulation does not prove production-grade privacy (no secure aggregation or
  differential privacy here); Vanna is advisory and executes nothing.
