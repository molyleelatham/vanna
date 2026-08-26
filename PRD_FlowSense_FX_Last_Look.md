# PRD: Vanna — Federated Last-Look & Execution Intelligence
**Collaborative Agent Hackathon — Cambridge, 26 Aug 2026**  
**Framework:** Flower Agent + SuperGrid &middot; **Tracks:** SuperGrid (Track 1) + Infrastructure (Track 2)  
**Compute:** Shared AMD Instinct MI300X model endpoints  
**Product type:** Broker-to-desk FX execution intelligence

---

## 1. Problem

FX desks frequently choose liquidity providers using displayed prices, but the tightest displayed quote is not always the cheapest executable quote. The realised outcome also depends on fill probability, rejection behaviour, quote age, response latency, slippage, volatility, and the liquidity provider's use of last look.

Last look gives a liquidity provider a short period after receiving a trade request to validate or reject the trade. It may protect the provider from stale prices and latency arbitrage, but it also creates an information asymmetry: the provider can see the client's request before deciding whether to execute. If the provider rejects trades selectively after the market moves in the client's favour, the client may receive an attractive quote without receiving an equivalent opportunity to trade at that quote.

No single FX desk can reliably identify these patterns across the market. Each desk sees only its own interactions with its liquidity providers. One desk may observe a high rejection rate, another may observe unusually long response times, and a third may observe that a liquidity provider's displayed prices are rarely executable during volatile periods. Individually, these observations are incomplete. Combining raw orders, client information, quotes, positions, or pricing logic is commercially unacceptable and may create privacy, competition, and collusion risks.

This creates a second problem: a collaborative network must not become a mechanism for coordinated trading behaviour. If desks receive live information about one another's intentions, they could coordinate liquidity withdrawal, spread changes, or counterparty exclusion. The system therefore needs to share useful historical execution intelligence while preventing the sharing of live trading intentions and collective instructions.

There is also a compliance requirement. Real orders and OTC transactions need durable, traceable records. The system cannot replace the real order ID, client record, UTI, or transaction record with an anonymous identifier. Instead, shared analytics need pseudonymization while the original desk retains the complete local audit trail.

**Core tension:** FX desks need cross-desk intelligence to measure asymmetric information and distinguish displayed prices from executable prices, but they cannot share raw trading data, cannot wait for a federation during live execution, and cannot allow collaborative intelligence to become coordinated market behaviour.

---

## 2. Solution

Vanna is a federated execution-intelligence product for FX brokers, execution desks, prime brokers, and liquidity providers. Each participant trains locally on its own quote, order, fill, rejection, latency, and slippage history. Flower aggregates model updates across participating desks so the shared model learns broader execution patterns without moving raw orders or client records.

The product predicts the **expected execution value** of each available liquidity provider instead of selecting the tightest displayed quote.

\[
\text{Expected Execution Value}_{LP}
=
P(\text{fill}) \times \text{price benefit}
-
\text{expected slippage}
-
\text{rejection cost}
-
\text{latency cost}
\]

The product then uses collaborative AgentApps to explain and govern the recommendation.

### The agent system

| Agent | Primary function | Output |
|---|---|---|
| **Vanna** | Predicts fill probability and expected execution cost | Recommended liquidity provider and expected cost |
| **LastLookAgent** | Measures rejection asymmetry, quote age, response latency, and post-request price movement | Last-look review signal, not an automatic misconduct finding |
| **CounterpartyRiskAgent** | Scores liquidity-provider reliability across execution conditions | Confidence, reliability factors, and route limits |
| **MarginAgent** | Monitors simulated credit, leverage, and settlement pressure | Exposure warning or human-review request |
| **ManipulationWatch** | Looks for artificial liquidity, coordinated quote behaviour, and cross-pair anomalies | Surveillance signal for review |
| **GovernanceAgent** | Monitors privacy, data access, participant behaviour, and possible coordinated outcomes | Suppression, escalation, or human-review decision |

For the hackathon, Vanna and LastLookAgent are the core working agents. CounterpartyRiskAgent should be the second working agent for the collaborative-agent demonstration. MarginAgent, ManipulationWatch, and GovernanceAgent can be lightweight extensions or visible prototype outputs if time permits.

### Commercial outcome

The primary customer value is not a regulatory report. It is better execution:

- Higher fill probability.
- Lower realised slippage.
- Fewer rejected orders.
- Better route selection.
- More accurate liquidity-provider negotiations.
- Identification of reliable liquidity during different volatility regimes.
- Evidence that a wider quote may be cheaper than a tighter but frequently rejected quote.

Compliance, auditability, and governance are built into the design so the product can be adopted by a desk without sacrificing commercial value.

---

## 3. Why this needs Flower + SuperGrid

| Requirement | Why Flower/SuperGrid is useful |
|---|---|
| Desks need to learn from a larger execution history | Federated training combines local learning without centralising raw orders |
| Client flow and liquidity-provider behaviour are commercially sensitive | Each desk retains its raw records and returns model updates rather than raw data |
| Live execution must remain fast | The latest model is stored and used locally; the live route does not wait for SuperGrid |
| Several specialised agents must collaborate | AgentApps can pass structured context between Vanna, LastLookAgent, and CounterpartyRiskAgent |
| Recommendations need to be explainable | The agents can return factors, confidence, data freshness, and review requirements |
| Privacy must not break compliance | Real order IDs and UTIs remain in the local desk audit store; shared IDs are pseudonymous |
| The network must resist free-riding | Contribution quality can be measured at federation level and used in an incentive mechanism |
| The network must resist collusion | Shared outputs can be delayed, bucketed, cohort-limited, and monitored by GovernanceAgent |

Flower provides the federation and AgentApp execution model. SuperGrid provides the federation workspace and execution environment for collaborative runs. The AgentApp itself must explicitly manage context and state: a run series does not automatically make previous messages visible to the model, so the application should store and replay only the structured state that later agents need.

The hackathon should use SuperGrid's simulation environment for the MVP. Five simulated desks can represent independent participants without requiring five production institutions. The AMD MI300X-hosted model endpoint can provide model access through the hackathon's configured Flower model endpoint. The system should not depend on unavailable Arm hardware or assume that AWS/Arm/AMD sponsor status means physical infrastructure is provisioned for the team.

---

## 4. What we build (hackathon scope)

1. **Synthetic FX execution generator** — Five simulated desks and three liquidity providers producing quotes, trade requests, fills, rejections, response latency, slippage, volatility regime, and post-request price movement.

2. **Last-look scenario generator** — Create three provider behaviours:
   - `LP_A`: tight displayed prices but elevated rejection and rejection asymmetry during fast markets.
   - `LP_B`: slightly wider quotes but high fill probability and stable latency.
   - `LP_C`: good in calm markets but unreliable during volatility.

3. **Local data stores** — Each simulated desk sees only its own execution history. Raw client IDs, local order IDs, UTIs, and full audit records remain local.

4. **Pseudonymization** — Generate a local pseudonym for shared analytics:

   ```python
   hash_id = HMAC(desk_secret, local_order_id)
   ```

   Shared features use buckets rather than raw values:

   ```text
   pair
   side
   size_bucket
   volatility_bucket
   quote_age_bucket
   latency_bucket
   fill_or_reject
   slippage_bucket
   ```

   This is pseudonymization, not irreversible anonymity. The hackathon must describe it accurately.

5. **Local execution model** — Each desk trains a small logistic-regression or tree-based model predicting:

   ```text
   fill_probability
   expected_slippage
   expected_latency
   rejection_probability
   post_request_price_movement
   ```

6. **Flower federated loop** — Each desk trains locally, sends model parameters, receives the aggregated model, and evaluates the model locally. Track model accuracy, validation loss, round duration, and bytes transferred.

7. **Vanna AgentApp** — Given an order and available quotes, ranks liquidity providers by expected execution value and recommends a route.

8. **LastLookAgent** — Compares acceptance and rejection behaviour across market conditions. It should identify elevated rejection asymmetry as a review signal, not make an automatic accusation.

9. **CounterpartyRiskAgent** — Reviews the proposed route and returns a reliability score, confidence level, evidence factors, and whether human approval is required.

10. **Context handoff** — Pass structured state between agents, for example:

    ```json
    {
      "order_context": {
        "pair": "EUR/USD",
        "side": "BUY",
        "size_bucket": "1m-5m"
      },
      "flowsense_recommendation": {
        "provider": "LP_B",
        "expected_cost_bps": 1.2,
        "confidence": "medium"
      },
      "last_look_signal": {
        "provider": "LP_A",
        "rejection_asymmetry": "elevated",
        "review_required": true
      }
    }
    ```

11. **Contribution mechanism** — Calculate a simple contribution score based on improvement to shared validation performance, data quality, and participation reliability. Present this as an incentive mechanism, not a proven formal Nash equilibrium.

12. **Anti-collusion controls** — Add minimum cohort thresholds, historical windows, bucketed features, no live order-intention sharing, local decisions, human review, and a governance warning if multiple desks would make the same provider decision at the same time.

13. **Dashboard** — Display:
    - Best displayed quote versus best expected executable quote.
    - Fill probability, rejection probability, latency, and slippage.
    - Local versus federated model performance.
    - Last-look asymmetry signal.
    - Agent handoff chain.
    - Raw records shared: zero.
    - Model updates aggregated: yes.
    - Recommendation confidence and human override.
    - Contribution score by simulated desk.

### Minimum viable build

If time is limited, build only:

```text
Five simulated desks
        ↓
Flower federated model
        ↓
Vanna recommendation
        ↓
LastLookAgent explanation
        ↓
Local human-controlled route
```

Do not make MarginAgent, ManipulationWatch, UTI reconciliation, or formal equilibrium analysis blockers for the first working demo.

---

## 5. Demo narrative (5:30pm slot)

1. **The problem, 30 seconds** — “The tightest FX quote is not always the best executable quote. Last look, rejection behaviour, latency, and asymmetric information can make a cheap displayed quote expensive in practice.”

2. **Show the fragmented desks** — Five desks have different local execution experiences. No desk sees the full provider-performance pattern.

3. **Show the misleading price** — LP_A offers the tightest displayed price, but its historical fill probability is low during fast markets. LP_B is slightly wider but more consistently executable.

4. **Show local-only routing** — One desk uses its local model and makes a lower-confidence recommendation based on incomplete observations.

5. **Run the Flower federation** — Each desk trains locally. Show that raw orders and client identities remain local while model updates are aggregated.

6. **Run Vanna** — The federated model recommends the provider with the best expected execution value rather than the tightest displayed price.

7. **Run LastLookAgent** — It explains that LP_A has elevated conditional rejection asymmetry during high-volatility periods. It explicitly says this is a review signal, not proof of misconduct.

8. **Run CounterpartyRiskAgent** — It validates the recommendation, gives confidence, shows data freshness, and confirms whether human review is required.

9. **Show the anti-collusion safeguard** — The recommendation is local to the requesting desk. The system does not broadcast “all desks should stop using LP_A.” A governance warning appears if identical routing changes would become too concentrated or synchronized.

10. **Show the commercial result** — Compare local-only routing against federated routing using actual generated evaluation results:

    ```text
    Local expected execution cost: [measured result] bps
    Federated expected execution cost: [measured result] bps
    Improvement: [measured result] bps
    ```

11. **Close** — “We improve each desk's execution decision without centralising its order flow, without putting federation latency in the live route, and without turning shared intelligence into coordinated market instructions.”

---

## 6. Success criteria for the day

- A real `flwr run` completes end-to-end on synthetic FX data across five simulated desks.
- The system trains local models and produces an aggregated federated model.
- The dashboard proves that raw orders, client identities, and local audit mappings do not leave each desk.
- Vanna recommends a route using expected execution value rather than displayed price alone.
- LastLookAgent identifies a conditional rejection pattern without automatically labelling it misconduct.
- At least one agent hands structured context to another agent through the AgentApp state mechanism.
- Local execution does not wait for a SuperGrid call during the simulated live-order decision.
- Local and federated model results are compared against a consistent test set.
- All displayed performance figures come from the actual demo run rather than invented claims.
- A governance control prevents automatic blacklisting and suppresses collective trading instructions.
- A human can override the recommendation, and every recommendation has a reason, confidence level, model version, and timestamp.
- The system remains usable if the federation or model endpoint is unavailable by falling back to the last known local model or deterministic routing rule.

---

## 7. Open risks

- **Last-look interpretation:** a high rejection rate is not automatically abusive. The model must control for volatility, quote age, order size, latency, and market movement before presenting asymmetry as a review signal.

- **Data realism:** synthetic data must contain meaningful provider behaviour. Randomly generated fills and rejections will not demonstrate asymmetric information convincingly.

- **Pseudonym limitations:** a desk-specific HMAC means the same real-world entity may have different pseudonyms across desks. The MVP should claim aggregate pattern learning, not cross-broker identity matching.

- **Collusion risk:** provider-specific rankings, synchronized alerts, or live routing instructions could create competition and conduct concerns. Use delayed historical windows, minimum cohorts, coarse buckets, local decisions, and GovernanceAgent review.

- **Blacklisting risk:** do not implement an automatic blacklist. Use “Counterparty Reliability Score,” keep it probabilistic and explainable, and require human approval for route restrictions or provider removal.

- **Agent overreach:** agents should recommend and explain; they should not automatically execute live trades, liquidate positions, file regulatory reports, or remove counterparties.

- **Federation latency:** SuperGrid and federated rounds are not suitable for the millisecond execution path. Use periodic background model updates and retain a local fallback model.

- **Flower Agent limitations:** the Agent layer is experimental; APIs may change. Account connectors may be restricted in collaborative federations, so use built-in or custom HTTP connectors for the hackathon.

- **Context and memory:** Flower run series do not automatically make prior messages visible to the model. Store compact, structured handoff state explicitly and keep tool loops bounded to stay within task limits.

- **Model drift:** FX behaviour changes during news, volatility shocks, and liquidity events. Track model freshness and confidence, and fall back to local rules when current conditions differ materially from training data.

- **Game-theory claims:** a contribution score is not the same as proving a Nash equilibrium. Present the mechanism as equilibrium-inspired and test the free-riding incentive empirically.

- **Compliance scope:** this is a prototype for execution intelligence, not a production AML, sanctions, market-abuse, or regulatory-reporting system. Real deployment would require legal, compliance, security, model-risk, and competition review.

- **Sponsor infrastructure assumptions:** AWS, AMD, and Arm are sponsor partners; do not assume that specific cloud instances or physical hardware are available. Use SuperGrid simulation and the provided model endpoint as the primary build path.
