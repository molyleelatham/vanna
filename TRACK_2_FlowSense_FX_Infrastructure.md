# Track 2: FlowSense FX Collaboration Infrastructure

## Project Summary

**FlowSense FX** is a reusable collaboration infrastructure for regulated, latency-sensitive agent systems.

The demonstration use case is FX execution and last-look analysis. Multiple FX desks train on private execution data, while Flower federates model improvements and SuperGrid runs collaborative AgentApps. The system helps a desk distinguish between the best displayed quote and the best executable quote without sharing raw client orders, trading intentions, or proprietary desk data.

The infrastructure is the product. FX is the proof case.

> **FlowSense FX enables agents from separate FX desks to collaborate safely and usefully without centralising raw order flow or blocking live execution.**

---

## 1. Track 2 Problem

Collaborative agents are difficult to use in regulated financial markets because agents need broader information than any one desk possesses, but the underlying data is commercially sensitive and time-critical.

In FX, the displayed quote is not always the best executable quote. A liquidity provider may quote aggressively but have a lower fill probability, longer response time, greater slippage, or elevated last-look rejection asymmetry. One FX desk cannot reliably observe these patterns across the market because it sees only its own execution history.

The obvious solution is to combine information across desks. However, raw sharing creates serious problems:

- Client identities may be exposed.
- Trading intentions may be revealed.
- Order size and strategy may become observable.
- Liquidity-provider relationships may be disclosed.
- Live signals could enable coordination or collusion.
- Regulatory identifiers and audit records must remain traceable.
- Network calls cannot be placed directly in a millisecond-sensitive execution path.

The missing capability is not simply another trading agent. It is the infrastructure that allows separate agents and desks to collaborate while controlling:

```text
privacy
latency
context
permissions
evidence
governance
failure
incentives
```

---

## 2. Track 2 Solution

FlowSense FX provides a collaboration layer with seven core capabilities:

1. **Privacy-controlled feature transformation** — converts raw local execution data into approved bucketed features before anything leaves a desk.
2. **Federated model training** — uses Flower to aggregate model updates without centralising raw orders.
3. **Structured agent evidence exchange** — gives agents typed, validated evidence instead of unrestricted access to raw data or unstructured conversations.
4. **Explicit context management** — stores and replays only the structured state that agents need for a handoff.
5. **Latency-aware local inference** — updates local models in the background so live routing never waits for SuperGrid or another desk.
6. **Governance and anti-collusion controls** — prevents the network from becoming a channel for coordinated market instructions or automatic counterparty exclusion.
7. **Contribution and resilience mechanisms** — rewards useful participation and provides fallbacks when the federation, connector, or model endpoint is unavailable.

The FX agents demonstrate what this infrastructure enables:

```text
FlowSense
    ↓
LastLookAgent
    ↓
CounterpartyRiskAgent
    ↓
GovernanceAgent
    ↓
Local execution recommendation
```

---

## 3. Technical Architecture

```text
┌──────────────────────────────────────────────────────┐
│ LOCAL FX DESK / SIMULATED SUPERNODE                 │
│                                                      │
│ Raw orders, client IDs, quotes, fills, UTIs          │
│ Local compliance records                              │
│                                                      │
│ Privacy Filter                                        │
│ Feature Bucketing                                     │
│ Local Model                                           │
│ Local Fast-Path Router                                │
└────────────────────────┬─────────────────────────────┘
                         │
                         │ approved historical features
                         │ model updates only
                         ▼
┌──────────────────────────────────────────────────────┐
│ FLOWER SUPERGRID COLLABORATION INFRASTRUCTURE        │
│                                                      │
│ SuperLink                                             │
│ SuperExec                                             │
│ Federated Aggregation                                 │
│ Model Versioning                                      │
│ Cohort and Privacy Controls                           │
│ Contribution Scoring                                  │
└────────────────────────┬─────────────────────────────┘
                         │
                         │ shared model and approved evidence
                         ▼
┌──────────────────────────────────────────────────────┐
│ AGENT EVIDENCE AND CONTEXT LAYER                     │
│                                                      │
│ Evidence Bus                                          │
│ Context Manager                                       │
│ Schema Validation                                     │
│ Permissions                                           │
│ Data Freshness                                        │
│ Confidence                                            │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│ COLLABORATIVE AGENTAPPS                              │
│                                                      │
│ FlowSense                                             │
│ LastLookAgent                                         │
│ CounterpartyRiskAgent                                 │
│ GovernanceAgent                                       │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│ LOCAL DESK DECISION                                  │
│                                                      │
│ Route, split, request another quote,                 │
│ use fallback, or request human approval              │
└──────────────────────────────────────────────────────┘
```

---

## 4. Component Design

### 4.1 Privacy Filter

The Privacy Filter runs at the local desk boundary.

Its responsibility is to prevent sensitive local records from being sent directly to the federation or another agent.

#### Raw local data

```text
client_id
account_id
real_order_id
UTI
exact_timestamp
exact_notional
exact_price
full quote history
position information
```

#### Shared representation

```text
currency_pair
buy_or_sell
size_bucket
volatility_bucket
quote_age_bucket
latency_bucket
fill_or_reject
slippage_bucket
post_request_price_movement_bucket
```

Example:

```python
def prepare_shared_features(order, execution):
    return {
        "pair": order.pair,
        "side": order.side,
        "size_bucket": bucket_size(order.notional),
        "volatility_bucket": bucket_volatility(order.volatility),
        "quote_age_bucket": bucket_age(order.quote_age_ms),
        "latency_bucket": bucket_latency(execution.latency_ms),
        "filled": execution.status == "FILLED",
        "slippage_bucket": bucket_slippage(execution.slippage_bps),
    }
```

The shared representation is designed to support model training without exposing unnecessarily precise details.

### 4.2 Pseudonymization

A desk may create a local pseudonym for correlation within its own analytics:

```python
hash_id = HMAC(desk_secret, local_order_id)
```

The mapping remains local:

```text
hash_id → real order ID → client/account record
```

The system must call this **pseudonymization**, not full anonymization. A desk that holds the secret may be able to resolve the value.

The MVP should not attempt cross-broker identity matching. Each desk may use its own pseudonym space, while federated learning operates on model updates and aggregate patterns.

### 4.3 Federated Model Layer

Each simulated desk trains locally on its own execution history.

The model predicts:

```text
fill_probability
rejection_probability
expected_slippage
expected_latency
post_request_price_movement
```

Flower coordinates the training process:

```text
1. SuperGrid starts a run.
2. Each desk receives the current model.
3. Each desk trains locally.
4. Each desk returns model parameters and approved metrics.
5. Flower aggregates the updates.
6. The new model is returned to each desk.
7. Each desk evaluates the model locally.
```

The live order path uses the locally cached model.

```text
Background path:
local data → federated training → updated local model

Live path:
order → local model → local recommendation
```

### 4.4 Agent Evidence Bus

The Evidence Bus allows agents to exchange structured outputs without exposing raw data.

Example evidence record:

```json
{
  "event_type": "execution_assessment",
  "run_id": "run-123",
  "source_agent": "FlowSense",
  "pair": "EUR/USD",
  "side": "BUY",
  "size_bucket": "1m-5m",
  "recommended_provider": "LP_B",
  "expected_fill_probability": 0.91,
  "expected_cost_bps": 1.2,
  "last_look_signal": "elevated",
  "confidence": "medium",
  "model_version": "fed-v7",
  "data_freshness_seconds": 420,
  "human_review_required": false
}
```

The bus validates:

- Schema.
- Field types.
- Required fields.
- Agent permissions.
- Data freshness.
- Model version.
- Confidence values.
- Whether a field can be shared.

The Evidence Bus should reject records containing prohibited fields such as raw client identity, full account number, or live trade intention.

### 4.5 Context Manager

Flower run series do not automatically make previous messages visible to a model. The Context Manager provides explicit state handling.

Conceptual interface:

```python
def save_evidence(run_id, agent_name, evidence):
    validate_schema(evidence)
    validate_permissions(agent_name, evidence)
    persist(run_id, agent_name, evidence)


def get_agent_context(run_id, agent_name):
    return {
        "current_order": load_current_order(run_id),
        "relevant_evidence": load_relevant_evidence(run_id, agent_name),
        "model_version": load_model_version(),
    }
```

Do not replay an entire conversation to every agent. Use compact structured state.

### 4.6 Governance Layer

The Governance Layer checks whether an agent output is safe to use.

Example:

```python
def evaluate_recommendation(recommendation):
    if recommendation["confidence"] == "low":
        return "HUMAN_REVIEW"

    if recommendation["data_freshness_seconds"] > 900:
        return "USE_LOCAL_FALLBACK"

    if recommendation["action"] == "AUTOMATIC_BLACKLIST":
        return "BLOCK"

    return "ALLOW_LOCAL_RECOMMENDATION"
```

Governance controls include:

- Confidence thresholds.
- Data-freshness checks.
- Human approval for high-impact decisions.
- No automatic blacklisting.
- No automatic regulatory filings.
- No collective trading instructions.
- Local independent decisions.
- Full model and decision logging.

### 4.7 Contribution Layer

Each desk receives a contribution score based on measurable value:

```python
contribution_score = (
    validation_improvement
    * data_quality
    * participation_reliability
)
```

This discourages free-riding, where a desk receives network benefits without contributing useful signal.

For the hackathon, describe this as an **equilibrium-inspired incentive mechanism**. Do not claim a formal Nash equilibrium unless the system implements and evaluates one.

---

## 5. Agent Responsibilities

### FlowSense

FlowSense is the primary commercial agent.

Input:

```text
currency pair
side
order-size bucket
available liquidity providers
current volatility regime
```

Output:

```text
recommended provider
expected fill probability
expected slippage
expected execution cost
confidence
reason
```

Example:

```text
Recommendation: LP_B

LP_A offers the tightest displayed price, but its predicted
fill probability is lower during the current volatility regime.
LP_B has a slightly wider quote but a higher expected executable value.
```

### LastLookAgent

LastLookAgent analyses:

- Acceptance rate.
- Rejection rate.
- Quote age.
- Response latency.
- Last-look duration.
- Market movement after the request.
- Volatility regime.
- Order size.
- Buy/sell direction.

A useful metric is:

\[
\text{Rejection Asymmetry}
=
\text{Reject Rate}_{\text{client-favourable}}
-
\text{Reject Rate}_{\text{client-unfavourable}}
\]

The output is a review signal, not an accusation:

```text
LP_A shows elevated conditional rejection asymmetry
for EUR/USD buy orders during high volatility.
This is a review signal, not proof of misconduct.
```

### CounterpartyRiskAgent

This agent produces an explainable reliability assessment:

```text
LP_B

Fill probability: High
Latency consistency: High
Expected slippage: Low
Rejection variance: Low
Data freshness: 6 minutes
Confidence: Medium
Human review: Not required
```

Use a probabilistic reliability score rather than a blacklist.

### MarginAgent

MarginAgent is an optional extension for the hackathon.

It estimates whether rapid price movement or correlated positions could create:

- Margin pressure.
- Forced-flow risk.
- Counterparty exposure.
- Settlement pressure.

Example:

```text
EUR/USD downside movement is increasing simulated margin pressure.
Reduce order size or request human review.
```

### ManipulationWatch

ManipulationWatch looks for:

- Rapid quote appearance and cancellation.
- Artificial liquidity.
- Cross-pair anomalies.
- Synchronized quote changes.
- Repeated pre-movement activity.
- Potential layering or wash-trade patterns.

It should flag patterns for review rather than automatically label a participant as abusive.

### GovernanceAgent

GovernanceAgent checks the collaborative system itself.

It flags:

- Synchronized routing changes.
- Coordinated liquidity withdrawal.
- Identical provider exclusions.
- Attempts to query rare participant data.
- Anomalous model updates.
- Insufficient participant count.
- Stale or low-confidence evidence.

Example:

```text
Five desks would independently route away from LP_A
within the same short window.

Possible explanation: market-wide volatility.
Control: suppress any collective instruction and require review.
```

---

## 6. Track 2 MVP

The minimum viable infrastructure should contain:

```text
Five simulated FX desks
        ↓
Privacy Filter
        ↓
Local execution models
        ↓
Flower federated aggregation
        ↓
FlowSense AgentApp
        ↓
LastLookAgent handoff
        ↓
Explainable local recommendation
```

### Required MVP features

- Five simulated desks.
- Three simulated liquidity providers.
- Synthetic quote and execution records.
- Local model training.
- Flower federated round.
- Local versus federated benchmark.
- Expected-execution-value routing.
- Last-look asymmetry signal.
- Structured agent handoff.
- HMAC pseudonym demonstration.
- Local fallback model.
- Human-review flag.
- Basic anti-collusion safeguard.

### Optional features

- CounterpartyRiskAgent.
- MarginAgent.
- ManipulationWatch.
- GovernanceAgent.
- Contribution scoring.
- UTI reconciliation.
- Privacy/noise dial.
- Dashboard visualisation.

Do not make the optional features blockers for the first end-to-end run.

---

## 7. Hackathon Demo

### Demo scenario

Create three liquidity providers:

```text
LP_A:
- Tightest displayed price
- Lower fill rate
- Higher rejection during fast markets
- Elevated rejection asymmetry

LP_B:
- Slightly wider displayed price
- Higher fill rate
- Stable latency
- Lower realised slippage

LP_C:
- Good in calm markets
- Poor during volatility
- High response-time variation
```

### Demo sequence

1. Show five desks with separate local execution histories.
2. Show a tight but unreliable quote from LP_A.
3. Run a local-only routing decision.
4. Show that the local desk has incomplete evidence.
5. Run Flower federated training.
6. Show that raw orders remain local.
7. Run FlowSense with the updated model.
8. Show that LP_B has better expected execution value.
9. Run LastLookAgent to explain LP_A's conditional rejection signal.
10. Run CounterpartyRiskAgent if available.
11. Show the local compliance/audit record remains intact.
12. Trigger a governance check against synchronized routing.
13. Disable the federation and demonstrate local fallback.

### Metrics to display

```text
Raw orders shared: 0
Client identities shared: 0
Exact trading intentions shared: 0
Model updates aggregated: yes
Federated round duration: [measured]
Local decision latency: [measured]
Federated model performance: [measured]
Local model performance: [measured]
Expected execution cost: [measured]
Human override available: yes
```

Use only values produced by the actual run.

---

## 8. Evaluation Benchmarks

Compare at least three approaches:

| Approach | Information used | Purpose |
|---|---|---|
| Local model | One desk's private data | Realistic baseline |
| Centralised model | All raw simulated data | Theoretical upper bound |
| Federated model | Model updates only | Proposed solution |

Measure:

- Fill prediction accuracy.
- Expected-cost prediction error.
- Fill-rate classification performance.
- Rejection prediction performance.
- Slippage prediction error.
- Local inference latency.
- Federation round duration.
- Model freshness.
- Resilience when one desk fails.

The expected qualitative result is:

```text
Local model < Federated model ≈ Centralised benchmark
```

The exact result must come from the test run.

---

## 9. Anti-Collusion Design

The infrastructure must improve independent decisions rather than coordinate the market.

### Do not share

- Live order intentions.
- Future trading plans.
- Exact current inventory.
- Exact live quotes.
- Planned spread changes.
- Unaggregated rejection events.
- Provider exclusion instructions.

### Use instead

- Delayed historical windows.
- Minimum participant thresholds.
- Bucketed features.
- Aggregate model updates.
- Local routing decisions.
- Human review for high-impact outputs.
- Governance monitoring.

Safe output:

```text
LP_B has higher expected executable value
for this desk's order and current market regime.
```

Unsafe output:

```text
All members should stop using LP_A.
```

### Minimum cohort rule

Only publish a shared insight if enough participants contributed to the relevant:

- Currency pair.
- Size bucket.
- Volatility regime.
- Time window.

If the cohort is too small:

```text
Shared insight unavailable.
Use local model only.
```

---

## 10. Compliance and Auditability

The system must preserve the complete local record:

```text
real order ID
client/account record
UTI
quote lifecycle
execution result
last-look timing
model version
agent recommendation
human override
final outcome
```

The shared layer may use:

```text
HMAC pseudonym
bucketed features
model parameters
aggregate performance metrics
```

The system should be able to answer:

1. What did the agent recommend?
2. Which model version produced the recommendation?
3. What evidence did the agent use?
4. How fresh was the evidence?
5. Was human review required?
6. What decision was ultimately made?
7. Which local record links the decision to the actual transaction?

This prototype is not a replacement for a production AML, sanctions, market-abuse, or regulatory-reporting system.

---

## 11. Failure and Fallback Design

Collaborative agents must fail safely.

### Federation unavailable

```text
Use last known local model.
```

### Model endpoint unavailable

```text
Use deterministic scoring and local routing rules.
```

### Connector timeout

```text
Return structured error.
Do not invent missing data.
```

### Low confidence

```text
Request human review.
```

### Stale model

```text
Reduce recommendation confidence.
Use local fallback or conservative route.
```

### Governance violation

```text
Block the unsafe action.
Preserve the evidence.
Escalate to review.
```

---

## 12. Build Sequence

### Phase 1: SuperGrid and Flower plumbing

1. Create a simulation federation.
2. Run the smallest Flower application.
3. Confirm the application bundle builds.
4. Confirm a remote run completes.
5. Confirm run input is received.

### Phase 2: Federated execution model

1. Generate synthetic FX events.
2. Partition events across five desks.
3. Train local models.
4. Aggregate model updates.
5. Evaluate local and federated models.
6. Record round metrics.

### Phase 3: Privacy infrastructure

1. Add HMAC pseudonyms.
2. Add feature bucketing.
3. Add prohibited-field validation.
4. Confirm real IDs do not enter shared payloads.

### Phase 4: Collaborative agents

1. Build FlowSense.
2. Add LastLookAgent.
3. Add structured context handoff.
4. Add confidence and evidence fields.
5. Add CounterpartyRiskAgent if time permits.

### Phase 5: Governance and demo

1. Add human-review conditions.
2. Add local fallback.
3. Add anti-collusion warning.
4. Add contribution score if time remains.
5. Build dashboard.
6. Rehearse the demo.

---

## 13. Track 2 Submission Statement

> **FlowSense FX introduces reusable infrastructure for regulated, latency-sensitive collaborative agents. The infrastructure transforms sensitive local execution records into approved bucketed features, trains shared models through Flower, passes validated structured evidence between AgentApps, manages explicit context, keeps live execution local, provides safe fallbacks, rewards useful participation, and prevents collaborative intelligence from becoming a coordinated market instruction. We demonstrate the infrastructure in FX by detecting when the tightest displayed quote is not the best executable quote because of last-look rejection asymmetry, latency, and slippage.**

---

## 14. Why This Is Track 2

The FX use case is only the application layer.

The Track 2 infrastructure is:

- Privacy filtering.
- Federated model training.
- Structured evidence exchange.
- Context management.
- Local inference caching.
- Latency-aware operation.
- Governance.
- Anti-collusion controls.
- Human oversight.
- Contribution incentives.
- Graceful failure handling.

These capabilities could later support other regulated collaborative-agent use cases, including:

- Cross-bank fraud detection.
- Insurance claims collaboration.
- Supply-chain finance.
- Healthcare analytics.
- Cybersecurity intelligence.
- Institutional trade surveillance.

FX last look is the proof that the infrastructure works in a commercially sensitive, latency-critical environment.

---

## 15. Limitations

- Flower Agent APIs may be experimental and may change between releases.
- SuperGrid simulation does not prove production security or production network latency.
- A local HMAC is pseudonymization, not irreversible anonymization.
- Local pseudonyms do not provide cross-desk identity matching.
- A high rejection rate does not prove unfair last-look behaviour.
- Synthetic execution data may not represent real FX market behaviour.
- A contribution score is not a formal proof of Nash equilibrium.
- Model updates may still leak information without appropriate privacy controls.
- Account connectors may be restricted in collaborative federations.
- A shared model should not automatically make AML, sanctions, blacklist, liquidation, or execution decisions.
- This prototype requires compliance, legal, security, model-risk, and competition review before any production deployment.
