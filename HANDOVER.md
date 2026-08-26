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
  ManipulationWatch, and GovernanceAgent
- Tests: 13 passing
- Deterministic live-path demo: working

The completed federation run executed three FedAvg rounds across five clients
in 12.81 seconds. Centralised evaluation loss moved from `0.6931` to `0.6646`.
The run reported zero raw records and zero client identities shared.

## Important locations

- `apps/federation/vanna_federation/client_app.py` — local desk training
- `apps/federation/vanna_federation/server_app.py` — FedAvg and artifact export
- `apps/agent/vanna_agent/agent_app.py` — current bounded agent chain
- `apps/agent/vanna_agent/domain.py` — deterministic routing and governance
- `apps/agent/vanna_agent/agents/` — all six independent typed agent roles
- `packages/vanna-core/src/vanna_core` — reusable domain contracts
- `scripts/sync_federation_artifact.py` — federation-to-agent handoff
- `scripts/local_demo.py` — endpoint-independent demo
- `TECH_ARCH.md` — architecture and integration contracts
- `AGENTS.md` — contribution and safety instructions

## Agent-team integration contract

Agent work should consume the approved provider-evidence JSON and produce a
strict structured handoff. It must not depend on direct access to desk-local
records. Numeric recommendations and governance remain deterministic; model
calls explain the supplied evidence.

The final orchestration agent should be merged last:

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

The orchestrator should validate run input, route typed state between agents,
enforce call/time limits, record model versions and failures, and invoke the
deterministic fallback when a child agent or endpoint fails.

## Running the infrastructure

```bash
cd apps/federation
uv run flwr run . --federation-config="num-supernodes=5" --stream
cd ../..
uv run python scripts/sync_federation_artifact.py
uv run python scripts/local_demo.py
```

Run the AgentApp on the configured Vanna SuperGrid federation:

```bash
cd apps/agent
uv run flwr run . supergrid --federation @molyleela/Vanna --stream
```

This requires available SuperGrid execution resources and a configured model
endpoint. Never add model keys or Flower authentication material to Git.

## Remaining work

1. Refine prompts or model-backed explanations for the completed deterministic
   agent roles without moving numerical decisions into the model.
2. Merge the orchestration layer after the agent and infrastructure interfaces
   are stable.
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
