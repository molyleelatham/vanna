# Vanna Handover

Last updated: 26 August 2026

## Current state

The core Flower infrastructure is working and ready for independent agent
development.

- Flower target: `1.35.0`
- SuperGrid login: completed
- SuperGrid federation: `@molyleela/Vanna`
- Local simulation: five SuperNodes
- Federation FAB: builds successfully
- Agent FAB: builds successfully
- Agent roles: Vanna, LastLookAgent, CounterpartyRiskAgent, MarginAgent,
  ManipulationWatch, GovernanceAgent, **OrchestratorAgent**
- Tests: 13 passing
- Deterministic live-path demo: working (full 6-agent chain)

The completed federation run executed three FedAvg rounds across five clients
in 12.81 seconds. Centralised evaluation loss moved from `0.6931` to `0.6646`.
The run reported zero raw records and zero client identities shared.

## Important locations

- `apps/federation/vanna_federation/client_app.py` — local desk training
- `apps/federation/vanna_federation/server_app.py` — FedAvg and artifact export
- `apps/agent/vanna_agent/agent_app.py` — **full 6-agent orchestrator entry point**
- `apps/agent/vanna_agent/agents/orchestrator.py` — **OrchestratorAgent sequencing all 6 agents**
- `apps/agent/vanna_agent/domain.py` — deterministic routing and governance
- `apps/agent/vanna_agent/agents/interfaces.py` — stable `assess()` protocols (`VannaLike`, `LastLookLike`, `CounterpartyRiskLike`). Prompt aliases recommend/analyse/review map to these.
- `apps/agent/vanna_agent/agents/` — all seven independent typed agent roles
- `apps/federation/vanna_federation/privacy.py` — desk-local HMAC vault + bucket helpers (never sent in Flower messages)
- `packages/vanna-core/src/vanna_core` — reusable domain contracts
- `scripts/sync_federation_artifact.py` — federation-to-agent handoff
- `scripts/local_demo.py` — endpoint-independent demo
- `TECH_ARCH.md` — architecture and integration contracts
- `AGENTS.md` — contribution and safety instructions
- `TODO.md` — prioritized completion plan

## Agent-team integration contract

Agent work should consume the approved provider-evidence JSON and produce a
strict structured handoff. It must not depend on direct access to desk-local
records. Numeric recommendations and governance remain deterministic; model
calls explain the supplied evidence.

The final orchestration agent is now merged:

```text
SuperGrid or SuperLink
    → OrchestratorAgent
    → Vanna agent
    → LastLookAgent
    → CounterpartyRiskAgent
    → MarginAgent
    → ManipulationWatch
    → GovernanceAgent
    → local recommendation or human review
```

The orchestrator validates run input, routes typed state between agents,
enforces call/time limits, records model versions and failures, and invokes the
deterministic fallback when a child agent or endpoint fails.

## Running the infrastructure

**Local simulation (reliable demo path):**

```bash
cd apps/federation
uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../..
uv run python scripts/sync_federation_artifact.py
uv run python scripts/local_demo.py
```

**SuperGrid federation (requires 5 SuperNodes connected to `@molyleela/Vanna`):**

```bash
cd apps/federation
uv run flwr run . supergrid --federation @molyleela/Vanna --stream
```

**SuperGrid AgentApp (requires SuperGrid resources + AMD model endpoint):**

```bash
cd apps/agent
export FLWR_MODEL_API_ENDPOINT="<full /v1/responses endpoint>"
export FLWR_MODEL_API_KEY="<key from hackathon Slack>"
export VANNA_MODEL_ID="<matching model ID>"
uv run flwr run . supergrid --federation @molyleela/Vanna --stream
```

**Local SuperLink + AgentApp (AMD Responses-compatible endpoint):**

```bash
export FLWR_MODEL_API_ENDPOINT="<full /v1/responses endpoint>"
export FLWR_MODEL_API_KEY="<key from hackathon Slack>"
export VANNA_MODEL_ID="<matching model ID>"
uv run flower-superlink --insecure
# In another terminal:
cd apps/agent
uv run flwr run . local-superlink --stream
```

Never add model keys or Flower authentication material to Git.

## SuperGrid SuperNode connection (for your friend)

To connect SuperNodes to the `@molyleela/Vanna` federation:

1. **Each SuperNode runs:**
   ```bash
   flower-supernode --superlink supergrid.flower.ai --federation @molyleela/Vanna
   ```

2. **Requirements:**
   - Flower 1.35.0+ installed
   - SuperGrid authentication configured (`flwr login supergrid`)
   - Network access to `supergrid.flower.ai`
   - 5 nodes must connect simultaneously (federation config: `min_train_nodes=5`)

3. **Troubleshooting:**
   - Run `flwr federation list` to see available federations
   - Run `flwr federation status @molyleela/Vanna` to check node connections
   - Nodes must stay connected for all 3 FedAvg rounds (~15-30s total)

## Merge points for later agent work

- Keep method name `assess`. Do not rename to recommend/analyse/review.
- Swap constructors only in `OrchestratorAgent.__init__` (`TODO(merge)`).
- Federation stays a separate FAB from the AgentApp.

## Remaining work

1. Refine prompts or model-backed explanations for the completed deterministic
   agent roles without moving numerical decisions into the model.
2. ~~Merge the orchestration layer~~ **DONE** — OrchestratorAgent wired in AgentApp.
3. Run the complete AgentApp on `@molyleela/Vanna` with the selected AMD model.
4. Add agent timeout, malformed-output, and child-failure integration tests.
5. Record only measured final demo metrics.

## Known limitations

- The current dataset is synthetic and does not establish production market
  behavior.
- Simulation does not prove production privacy, security, or network latency.
- Model updates can leak information without production secure aggregation or
  differential-privacy controls.
- A last-look signal is not evidence of misconduct.
- Vanna is advisory and must not execute trades or coordinate participant
  behavior automatically.
