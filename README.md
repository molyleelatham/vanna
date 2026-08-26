# Vanna

Vanna is a Flower-powered, federated FX execution-intelligence prototype for
the 2026 Cambridge Collaborative Agent Hackathon. It demonstrates that the
tightest displayed quote is not always the best executable quote.

Five simulated desks train on private execution histories. Flower aggregates
their model updates. Six typed agent roles cover execution value, last look,
counterparty reliability, margin pressure, manipulation signals, and
governance, sequenced by the merged OrchestratorAgent with per-agent
`explain()` contributions. Raw orders, client identities, UTIs, and live
intentions never enter the shared payload.

## Architecture

```text
Five private desk partitions
        │ model updates only
        ▼
Flower ClientApp + ServerApp (FedXgbBagging; opt-in FedAvg + SecAgg+ mode)
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
apps/agent/            all six typed agent roles and current AgentApp entry point
apps/dashboard/        standalone React dashboard for the demo and evidence review
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

## Run the demo dashboard

The dashboard is a terminal-style React application; it does not sit in either
Flower FAB. A localhost-only gateway retrieves a public Alpha Vantage FX quote
when configured and invokes the deterministic AgentApp domain path against the
approved evidence artifact.

```bash
# Terminal 1: optional public FX quote source (never commit this value)
export ALPHAVANTAGE_API_KEY="<key>"

# Terminal 2: local gateway (port 8010; port 8000 belongs to SuperLink)
cd apps/agent
uv run python -m vanna_agent.gateway

# Terminal 3: browser UI (port 5173)
cd apps/dashboard
npm install
npm run dev
```

The ticket accepts only pair, side, size bucket, volatility, and available
providers. `Assess order` returns a deterministic, governed recommendation;
`Send to approval queue` writes a local non-executable audit record. It never
sends a broker/OMS order. Without an Alpha Vantage key or when the provider
fails, the quote strip labels its safe local fallback.

## Run the real five-desk federation

```bash
cd apps/federation
uv sync
uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../..
uv run python scripts/sync_federation_artifact.py
```

The run performs three federated rounds, prints measured loss/accuracy and
round duration, and writes
`apps/federation/artifacts/generated/provider_evidence.json`.
The sync script copies only that approved aggregate artifact into the AgentApp.

### Secure aggregation mode (SecAgg+)

Add `--run-config "secure-aggregation=true"` to run the federation under
Flower's SecAgg+ protocol: every desk update is masked on the client and the
server only recovers the weighted average across desks — individual updates
are never visible to the server.

```bash
cd apps/federation
uv run flwr run . --federation-config="num-supernodes=5" \
  --run-config "secure-aggregation=true" --stream
```

Secure mode trains the transparent NumPy logistic model with FedAvg (SecAgg+
is a summation protocol and cannot merge XGBoost trees, so the default
bagging path is unchanged). With `num-shares=5` and
`reconstruction-threshold=3`, a round completes even if up to two nodes drop
out. The exported evidence artifact has the identical schema in both modes.
The flag works for the SuperGrid run as well.

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

Measured on 2026-08-26: SuperGrid federation run `12309076582906127164`
(3 rounds, 5/5 nodes, 0 failures, ~2.5 min including FAB upload); SuperGrid
AgentApp run `1896158749138907396` (~22 s); local SuperLink + Qwen3.5-397B
narration (~69 s); deterministic local demo (<1 s); SecAgg+ secure-mode
simulation (3 rounds, 5/5 nodes, 16.4 s). Use only metrics printed by the
actual run. This prototype does not execute trades, blacklist providers,
coordinate desks, or replace production compliance systems.

## Source documents

- [Product requirements](PRD_FlowSense_FX_Last_Look.md)
- [Track 2 infrastructure design](TRACK_2_FlowSense_FX_Infrastructure.md)
- [Flower framework notes](SKILL_Flower_Framework_Documentation.md)

The legacy source-document filenames predate the final name; their content,
the implementation, and the submission name use Vanna.
