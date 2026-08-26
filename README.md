# Vanna

Vanna is a Flower-powered, federated FX execution-intelligence prototype for
the 2026 Cambridge Collaborative Agent Hackathon. It demonstrates that the
tightest displayed quote is not always the best executable quote.

Five simulated desks train on private execution histories. Flower aggregates
their model updates. Six typed agent roles cover execution value, last look,
counterparty reliability, margin pressure, manipulation signals, and
governance. OrchestratorAgent sequences those roles through stable `assess()`
interfaces so later main-branch agent work is a class swap, not a rename.
Raw orders, client identities, UTIs, and live intentions never enter the shared
payload. Live decisions use `scripts/local_demo.py` and do not wait on SuperGrid.

## Architecture

```text
Five private desk partitions
        │ model updates only
        ▼
Flower ClientApp + ServerApp (FedAvg)
        │ approved aggregate evidence
        ▼
Vanna Agent → specialist typed handoffs
        ├── LastLookAgent
        ├── CounterpartyRiskAgent
        ├── MarginAgent
        └── ManipulationWatch
                 │
                 ▼
GovernanceAgent → recommendation / fallback / human review
```

Flower App Bundles cannot combine an `AgentApp` with a
`ServerApp`/`ClientApp` pair, so the repository intentionally contains two
independent Flower apps:

```text
apps/federation/       five-desk Flower simulation and evidence export
apps/agent/            AgentApp + OrchestratorAgent (`assess()` merge points)
packages/vanna-core/   reusable privacy, schemas, scoring, and governance
scripts/               artifact handoff and deterministic live-path demo
tests/                 privacy, federation, routing, governance, and agent tests
```

## Quick start

Requires Python 3.11+ and `uv`.

```bash
uv sync
uv run pytest -q
uv run python scripts/local_demo.py
```

The local demo is the latency-safe path: it never waits for Flower or a model
endpoint and can use the last approved artifact.

## Run the real five-desk federation

```bash
cd apps/federation
uv sync
uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../..
uv run python scripts/sync_federation_artifact.py
```

The run performs three FedAvg rounds, prints measured loss/accuracy and round
duration, and writes `apps/federation/artifacts/generated/provider_evidence.json`.
The sync script copies only that approved aggregate artifact into the AgentApp.

## Build and run the AgentApp

Build the Flower App Bundle:

```bash
cd apps/agent
uv sync
uv run flwr build
```

For SuperGrid:

```bash
uv run flwr login supergrid
uv run flwr run . supergrid --stream
```

For the hackathon's local SuperLink and AMD Responses-compatible endpoint:

```bash
export FLWR_MODEL_API_ENDPOINT="<full /v1/responses endpoint>"
export FLWR_MODEL_API_KEY="<key from the hackathon Slack>"
export VANNA_MODEL_ID="<matching model ID>"
uv run flower-superlink --insecure
```

Run from another terminal using the local SuperLink connection described in
the current Flower Agent documentation. Qwen does not require
`FLWR_MODEL_API_KEY`; unset it before starting SuperLink when using that
endpoint. Restart SuperLink after changing models.

The default structured order is:

```json
{
  "pair": "EUR/USD",
  "side": "BUY",
  "size_bucket": "1m-5m",
  "volatility": "high",
  "available_providers": ["LP_A", "LP_B", "LP_C"]
}
```

Override it with `--run-config 'agent.input={...}'`.

## Demo flow (3–5 minutes)

1. Show five isolated desk partitions and the privacy tests.
2. Show LP_A's tight quote and the local-only uncertainty.
3. Run the Flower federation and point out `raw-records-shared: 0`.
4. Sync the aggregate artifact and run Vanna.
5. Show LP_B winning on expected executable cost.
6. Show LastLook flagging LP_A's conditional asymmetry as a review signal only.
7. Show the governance result, human control, and deterministic fallback.

Use only metrics printed by the actual run. This prototype does not execute
trades, blacklist providers, coordinate desks, or replace production
compliance systems.

## Source documents

- [Product requirements](PRD_FlowSense_FX_Last_Look.md)
- [Track 2 infrastructure design](TRACK_2_FlowSense_FX_Infrastructure.md)
- [Flower framework notes](SKILL_Flower_Framework_Documentation.md)

The legacy source-document filenames predate the final name; their content,
the implementation, and the submission name use Vanna.
