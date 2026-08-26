# Skill: Flower Framework and Documentation

## Purpose

This skill provides a practical reference for building, running, debugging, and explaining applications with the Flower Framework, Flower Agent, and Flower SuperGrid.

It is designed for hackathon teams building collaborative agent systems, federated learning applications, and privacy-preserving multi-party workflows.

## Scope

Use this skill when working with:

- Flower federated learning applications.
- Flower `ClientApp` and `ServerApp` projects.
- Flower Agent `AgentApp` applications.
- Flower SuperGrid federations.
- SuperLink, SuperNode, and SuperExec.
- Flower App Bundles (FABs).
- Flower connectors and tool calls.
- Collaborative agent handoffs.
- Federated model training.
- Local inference and background federation.
- Privacy, latency, governance, and auditability.

## Core Principles

1. Keep sensitive data local.
2. Send model updates or approved aggregate features rather than raw records.
3. Keep real-time inference separate from slower federated training.
4. Treat pseudonymization as different from anonymization.
5. Keep regulatory identifiers and audit records at the data owner's boundary.
6. Bound all agent tool loops.
7. Make agent outputs explainable and reviewable.
8. Design a local fallback when the federation or model endpoint is unavailable.
9. Never assume that a run series automatically gives a model conversational memory.
10. Confirm current API behaviour against the installed Flower version.

## Flower Architecture

### SuperLink

SuperLink is the central coordination process in a deployed Flower federation.

Responsibilities:

- Coordinates federated learning runs.
- Forwards tasks to participating SuperNodes.
- Receives results from SuperNodes.
- Manages federation state.
- Provides control and application communication APIs.
- Coordinates execution through SuperExec.

Typical logical interfaces include:

| Interface | Typical role |
|---|---|
| ServerApp communication | Connects server-side application processes |
| Fleet communication | Connects SuperNodes and distributes tasks |
| Control API | Administrative operations and run control |
| Simulation communication | Coordinates simulation-runtime execution |

Do not hard-code ports or assume a particular API layout without checking the installed version and deployment configuration.

### SuperNode

A SuperNode represents a participating data owner or compute participant.

In a financial use case, one SuperNode can represent:

- An FX desk.
- A broker.
- A liquidity provider.
- A regional entity.
- A simulated participant.

Responsibilities:

- Connects to SuperLink.
- Polls for work.
- Manages local application execution.
- Provides access to local data for a `ClientApp`.
- Returns local results or model updates.

Recommended mapping:

```text
One broker or desk = one logical SuperNode
```

The mapping is a design convention. A SuperNode does not automatically guarantee that the underlying data is isolated; isolation must be enforced by deployment and application code.

### SuperExec

SuperExec manages isolated application execution.

It can launch and manage:

- `ServerApp` processes.
- `ClientApp` processes.
- `AgentApp` processes.

Responsibilities:

- Starts application processes.
- Stops processes.
- Handles execution lifecycle.
- Provides process or container isolation, depending on configuration.
- Supports per-execution security mechanisms.

Design implication:

```text
Long-lived infrastructure:
SuperLink + SuperNode

Short-lived workload:
ServerApp + ClientApp + AgentApp
```

### SuperGrid

SuperGrid is the managed collaboration workspace around Flower federations.

A federation can contain:

- Members.
- Runs.
- Run series.
- Execution resources.
- Participating nodes.
- Application execution permissions.

SuperGrid supports different runtime models, including:

- Simulation runtime for fast experiments and hackathon demonstrations.
- Deployment runtime for connected distributed SuperNodes.

For a hackathon, prefer simulation runtime unless the team already has deployment credentials and working nodes.

### Flower App Bundle

A Flower App Bundle, or FAB, packages a Flower application for execution.

A FAB can contain:

- Application code.
- Configuration.
- Dependencies or dependency metadata.
- Component references.

Use a FAB when an application must be built and executed through a remote Flower environment.

## Federated Learning Concepts

### ClientApp

A `ClientApp` contains participant-side federated learning logic.

Typical responsibilities:

1. Load local data.
2. Receive the current global model.
3. Train locally.
4. Evaluate locally.
5. Return model parameters and metrics.

Financial example:

```text
One FX desk receives the current execution model,
trains it on its own quote and fill history,
and returns updated model parameters.
```

### ServerApp

A `ServerApp` contains server-side federated learning logic.

Typical responsibilities:

- Select a federated strategy.
- Configure rounds.
- Aggregate client updates.
- Evaluate global model performance.
- Track metrics.
- Configure participant sampling.

### FedAvg

`FedAvg` aggregates client model updates, usually weighting them by the amount of local training data.

Basic conceptual process:

```text
Global model → local training → model updates → aggregation → new global model
```

Do not equate model aggregation with raw-data aggregation. The design should make clear what crosses the federation boundary.

### Secure Aggregation

Secure aggregation is intended to prevent the server from inspecting individual participant updates.

Use it where the deployment supports it and verify the exact Flower version and strategy configuration.

For a hackathon, a noise dial or simulated aggregation overhead must be labelled as a demonstration stand-in if full secure aggregation is not implemented.

### Simulation Runtime

Simulation runtime lets a team represent multiple participants on one machine or managed environment.

Use it to test:

- Five simulated broker desks.
- Different local data partitions.
- Local training.
- Aggregation.
- Dropout or straggler behaviour.
- Privacy/latency trade-offs.

Simulation does not prove production network performance or production security.

## Flower Agent

### AgentApp

An `AgentApp` contains agent execution logic that Flower can run locally or through SuperGrid.

An AgentApp can:

- Read run input.
- Call a model endpoint.
- Request connector tool schemas.
- Execute connector calls.
- Maintain structured state.
- Return a final response.
- Pass work to another agent through explicit application state.

The AgentApp is separate from the normal `ServerApp` and `ClientApp` execution model.

### AgentSession

Agent execution uses an agent session abstraction. The exact APIs may change because Flower Agent is experimental.

Use the installed documentation and source for the current version before relying on undocumented functions.

### Common Agent APIs

Current Flower Agent examples commonly use concepts equivalent to:

```python
agent.responses.create(...)
agent.connectors.tools(...)
agent.connectors.call(...)
```

These names and signatures must be checked against the installed version.

A model request normally includes:

- Model name.
- Input messages.
- Instructions.
- Tool definitions.
- Tool choice.
- Stream option.

### Run input

AgentApp input can be read from run configuration, commonly through a structure similar to:

```python
context.run_config.get("agent.input")
```

Recommended input format:

```json
{
  "pair": "EUR/USD",
  "side": "BUY",
  "size_bucket": "1m-5m",
  "available_providers": ["LP_A", "LP_B", "LP_C"]
}
```

Prefer structured JSON over forcing the agent to extract all fields from natural language.

## Agent Memory and Context

### Important distinction

A run series groups related runs and may preserve state, but it does not automatically make previous messages visible to the model.

The AgentApp must:

1. Read persisted state.
2. Select the relevant history.
3. Add the current input.
4. Send the assembled messages to the model.
5. Persist the updated state.

Conceptual pattern:

```python
messages = load_state(context)
messages.append(current_user_message)
response = call_model(messages)
save_state(context, messages, response)
```

### Recommended financial state

Do not store a complete conversation by default. Store compact structured state:

```json
{
  "order_context": {},
  "model_version": "v12",
  "recommendation": {},
  "last_look_signal": {},
  "confidence": "medium",
  "human_review_required": false,
  "timestamp": "..."
}
```

This is cheaper, easier to audit, and less likely to exceed context or task-time limits.

### Agent handoff

Pass only the information the next agent needs.

Example:

```text
FlowSense → LastLookAgent

- Order pair
- Side
- Size bucket
- Recommended LP
- Expected fill probability
- Expected slippage
- Model confidence
```

Do not pass unnecessary client identity or raw order history.

## Connectors

### Connector types

Connectors expose runtime-provided tools to an AgentApp.

They can provide:

- Market data.
- Order-flow statistics.
- Execution history.
- Document retrieval.
- Logging.
- Risk-system queries.
- Web search or web fetch.

### Tool discovery

An AgentApp may request available tool schemas so the model knows what it can call.

Conceptual pattern:

```python
tools = agent.connectors.tools(TOOL_REFS)
```

### Tool execution

A model can request a tool call. The AgentApp should execute it explicitly and return the result to the model.

Conceptual pattern:

```python
result = agent.connectors.call(tool_call)
```

### Connector design rules

- Keep credentials out of application code.
- Return typed, bounded responses.
- Validate input parameters.
- Apply timeouts.
- Log failures.
- Avoid returning raw client data.
- Use bucketed or aggregated fields where possible.
- Provide clear error messages to the agent.

### Connector failure handling

Do not crash the entire AgentApp if a connector fails.

Return a structured error:

```json
{
  "error": true,
  "connector": "market_data",
  "message": "Market data unavailable",
  "fallback": "Use last known snapshot"
}
```

The agent should explain uncertainty rather than inventing a result.

### Tool loop limit

Every tool-using AgentApp should define a maximum number of turns:

```python
MAX_TOOL_TURNS = 3
```

The exact value depends on the task, but it must be finite.

When the limit is reached:

- Stop calling tools.
- Produce a final answer.
- Explain missing information if necessary.
- Do not keep retrying indefinitely.

## Collaborative Agent Pattern

### Recommended architecture

```text
User request
     ↓
FlowSense AgentApp
     ↓ structured state
LastLook AgentApp
     ↓ structured state
CounterpartyRisk AgentApp
     ↓
Human-controlled execution recommendation
```

For FX execution:

- FlowSense estimates expected execution value.
- LastLookAgent analyses rejection asymmetry.
- CounterpartyRiskAgent checks provider reliability.
- GovernanceAgent checks safety and collusion conditions.

### Do not create an agent for every noun

Start with one working agent and add a second only after the first is reliable.

Good MVP:

```text
FlowSense + LastLookAgent
```

Optional extensions:

```text
CounterpartyRiskAgent
MarginAgent
ManipulationWatch
GovernanceAgent
```

## FX Reference Architecture

```text
┌──────────────────────────────────────────────┐
│ Local FX Desk                                │
│                                              │
│ Raw orders, client IDs, UTIs, quotes, fills  │
│ Local model and local compliance records     │
│                                              │
│ Fast local routing decision                  │
└──────────────────────┬───────────────────────┘
                       │
                       │ delayed, bucketed features
                       ▼
┌──────────────────────────────────────────────┐
│ Flower SuperGrid Federation                  │
│                                              │
│ SuperLink                                   │
│ SuperExec                                   │
│ Federated model aggregation                 │
│ Participant and run coordination             │
└──────────────────────┬───────────────────────┘
                       │
                       │ updated model / aggregate signal
                       ▼
┌──────────────────────────────────────────────┐
│ Local AgentApps                             │
│                                              │
│ FlowSense                                   │
│ LastLookAgent                               │
│ CounterpartyRiskAgent                       │
│ GovernanceAgent                             │
└──────────────────────────────────────────────┘
```

## Real-Time and Federated Paths

### Real-time path

```text
Order → local model → agent recommendation → local execution
```

No SuperGrid call should be required for each live order.

### Federated path

```text
Local execution history
    → local training
    → Flower aggregation
    → updated model
    → local deployment
```

Federated training can run:

- Periodically.
- After a batch of trades.
- When model error increases.
- After a regime change.

### Fallback path

```text
If shared model unavailable:
    use last known local model

If confidence is low:
    use deterministic routing rule

If risk is high:
    require human approval
```

## Last-Look Modelling

### Required fields

Use event data such as:

```text
quote_id
order_id
currency_pair
side
notional_bucket
quoted_price
quote_timestamp
request_timestamp
response_timestamp
last_look_duration
accepted_or_rejected
fill_price
market_price_after_window
reject_reason
```

### Core metrics

Acceptance rate:

\[
\text{Acceptance Rate}
=
\frac{\text{Accepted Requests}}{\text{Total Requests}}
\]

Rejection asymmetry:

\[
\text{Rejection Asymmetry}
=
\text{Reject Rate}_{\text{client-favourable}}
-
\text{Reject Rate}_{\text{client-unfavourable}}
\]

Treat elevated asymmetry as a review signal, not proof of misconduct.

### Controls

Control for:

- Volatility.
- Quote age.
- Order size.
- Currency pair.
- Direction.
- Response latency.
- Market movement.
- Liquidity conditions.

A high rejection rate alone is insufficient to establish unfair behaviour.

## Privacy and Identity

### Pseudonymization

A local desk may generate:

```python
hash_id = HMAC(desk_secret, local_order_id)
```

The raw mapping remains local.

This is pseudonymization, not full anonymization, because the originating desk may be able to resolve the identifier.

### Local-only compliance records

Keep locally:

- Client identity.
- Account number.
- Real order ID.
- UTI.
- Full quote and trade lifecycle.
- Compliance decision.
- Human override.

### Shared features

Prefer:

- Currency-pair categories.
- Size buckets.
- Latency buckets.
- Slippage buckets.
- Delayed time windows.
- Aggregated provider behaviour.

Avoid sharing exact live orders or trading intentions.

## Compliance and Anti-Collusion

### Prohibited or high-risk outputs

Avoid generating:

```text
All desks should stop using LP_A.
```

Avoid automatic:

- Blacklisting.
- Counterparty exclusion.
- Trade execution.
- Liquidation.
- Regulatory filing.
- Sanctions decisions.

### Preferred outputs

```text
LP_A has lower predicted execution reliability
for this order type and volatility regime.
Confidence: medium.
Human review: recommended.
```

### Anti-collusion controls

Implement or describe:

- Delayed historical data.
- Minimum cohort sizes.
- Coarse feature buckets.
- No live order-intention sharing.
- Local independent routing decisions.
- Human review for high-impact actions.
- Governance monitoring for synchronized decisions.
- No global automatic blacklist.

### GovernanceAgent

A GovernanceAgent can flag:

- Synchronized routing changes.
- Coordinated liquidity withdrawal.
- Identical provider exclusions.
- Attempts to query rare participant data.
- Anomalous participant updates.
- Excessive access to competitor-sensitive information.

Its output should be a warning or escalation, not a trading instruction.

## Incentives and Game Theory

Federated systems face a free-rider problem: a participant may contribute little while receiving shared model benefits.

For a hackathon, use an incentive score rather than claiming a formal equilibrium proof.

Example:

\[
\text{Contribution Score}_i
=
\text{Model Improvement}_i
\times
\text{Data Quality}_i
\times
\text{Participation Reliability}_i
\]

Possible benefits for useful contributors:

- Higher-confidence network insights.
- Better model resolution.
- Higher federation reputation.
- Greater access to aggregate metrics.

Call this an equilibrium-inspired mechanism unless the system actually implements formal equilibrium computation.

## Recommended Project Structure

A typical project can be organised as:

```text
project/
├── pyproject.toml
├── README.md
├── src/
│   └── fx_agents/
│       ├── __init__.py
│       ├── agent_app.py
│       ├── flowsense.py
│       ├── last_look.py
│       ├── state.py
│       ├── schemas.py
│       └── connectors.py
├── data/
│   └── synthetic/
├── tests/
│   ├── test_hashing.py
│   ├── test_features.py
│   └── test_routing.py
└── README.md
```

Use the project structure generated by the current Flower template if it differs. Do not rely on an old template without checking the installed release.

## Configuration Checklist

Before running remotely, verify:

- Flower version is pinned.
- AgentApp entry point is correct.
- Run input is defined.
- Model endpoint environment variable is set before starting required infrastructure.
- Connector references are valid.
- Federation ID is correct.
- User is a member of the federation.
- Application is built into a valid FAB.
- Tool loops have a hard maximum.
- Timeouts are configured.
- State is compact and serializable.
- Secrets are not committed to Git.

## Generic CLI Workflow

The exact commands may differ by installed version, but the workflow is generally:

```bash
uv sync
uv run flwr build
uv run flwr login supergrid
uv run flwr federation list supergrid
uv run flwr run . supergrid --federation @account/federation
```

For an AgentApp run, configure the input through run configuration, for example:

```bash
uv run flwr run . supergrid \
  --federation @account/federation \
  --run-config 'agent.input={"pair":"EUR/USD","side":"BUY"}'
```

Always check the current CLI help:

```bash
uv run flwr --help
uv run flwr run --help
```

## Testing Strategy

### Unit tests

Test:

- HMAC pseudonym generation.
- Feature bucketing.
- Expected execution value.
- Rejection asymmetry.
- Confidence calculation.
- Fallback routing.
- State serialization.
- Tool-call validation.

### Federated tests

Test:

- One local participant.
- Multiple participants.
- Missing participant.
- Slow participant.
- Invalid update.
- Empty local dataset.
- Model aggregation.
- Evaluation on a held-out dataset.

### Agent tests

Test:

- Valid order input.
- Missing market data.
- Connector timeout.
- Tool-loop limit.
- Low-confidence recommendation.
- Human-review escalation.
- Handoff from FlowSense to LastLookAgent.

### Demo acceptance test

The demo must prove:

```text
Raw orders shared: 0
Client identities shared: 0
Model updates aggregated: yes
Live route blocked by federation: no
Recommendation explainable: yes
Human override available: yes
```

## Common Mistakes

### Mistake: putting SuperGrid in the live order path

Bad:

```text
Live order → SuperGrid → other desks → route
```

Better:

```text
Background federation → updated local model
Live order → local model → route
```

### Mistake: calling a hash anonymous

A keyed hash is usually a pseudonym. Explain who holds the key and who can resolve it.

### Mistake: relying on chat memory

Run series state does not automatically become model input. Persist and replay required state explicitly.

### Mistake: unlimited agent loops

Always use a maximum tool-turn count and a total timeout.

### Mistake: using displayed price as execution quality

Compare fill probability, rejection risk, latency, and slippage.

### Mistake: treating every rejection as misconduct

Condition rejection analysis on market and order circumstances.

### Mistake: building a literal blacklist

Use a probabilistic, explainable counterparty reliability score with human review.

### Mistake: claiming a formal Nash equilibrium without testing it

Use “equilibrium-inspired incentive mechanism” unless formally demonstrated.

### Mistake: overbuilding agents

One excellent working agent is better than six disconnected stubs.

## Hackathon Build Sequence

### Phase 1: infrastructure

1. Create or join a SuperGrid simulation federation.
2. Run the simplest Flower application.
3. Verify the CLI, federation, and application bundle.
4. Confirm that a run completes successfully.

### Phase 2: federated model

1. Generate synthetic FX execution data.
2. Partition it across five simulated desks.
3. Train local models.
4. Aggregate model updates.
5. Compare local and federated performance.

### Phase 3: agent

1. Build FlowSense.
2. Add expected execution value.
3. Add LastLookAgent.
4. Add structured context handoff.
5. Add confidence and explanations.

### Phase 4: governance

1. Add local audit logs.
2. Add HMAC pseudonyms.
3. Add anti-collusion controls.
4. Add human review.
5. Add local fallback.

### Phase 5: demo

Show:

1. Misleading tight quote.
2. Local-only recommendation.
3. Flower federated round.
4. Federated recommendation.
5. Last-look explanation.
6. Privacy boundary.
7. Anti-collusion safeguard.
8. Commercial execution result.

## Limitations

Flower Agent and related APIs may be experimental and can change incompatibly between releases.

Current limitations may include:

- Agent APIs changing between versions.
- Incomplete persistent federation-agent management.
- Limited persistent CLI conversation restoration.
- Connector restrictions in collaborative federations.
- Account connectors being restricted to personal-workspace execution.
- No guarantee that run-series state is automatically visible to the model.
- Simulation runtime not proving production latency or security.
- Secure aggregation availability depending on strategy and deployment.
- SuperGrid availability, quotas, credit limits, or task timeouts affecting runs.
- External model endpoints becoming unavailable or rate-limited.

Treat documentation, CLI help, and the installed package version as authoritative.

## Reference Sources

Use the current official documentation before implementation:

- Flower Agent documentation: https://flower.ai/docs/agent/
- Agent architecture: https://flower.ai/docs/agent/index.html
- Collaborative agent tutorial: https://flower.ai/docs/agent/tutorials/build-a-collaborative-agent.html
- Agents and federations: https://flower.ai/docs/agent/how-to-guides/use-agents-and-federations.html
- Flower framework documentation: https://flower.ai/docs/
- Flower architecture: https://flower.ai/docs/framework/explanation-flower-architecture.html
- Network communication: https://flower.ai/docs/framework/ref-flower-network-communication.html
- SuperGrid announcement and runtime overview: https://flower.ai/blog/2025-09-25-flower-supergrid

The official documentation should be checked for version-specific commands, schemas, security settings, and deployment capabilities.
