# PRD: Federated Equity Intelligence Network
**Collaborative Agent Hackathon — Cambridge, 26 Aug 2026**
**Framework:** Flower (Federated AI + Agent) &middot; **Compute sponsors:** AWS &middot; AMD &middot; Arm &middot; **Track:** Open Exploration

---

## 1. Problem

Equity markets are fragmented across dozens of venues and internalizing brokers, so no single desk or broker ever sees the full order-flow picture for a stock — only its own slice. This fragmentation isn't just an inconvenience: it's the mechanism that lets informed or manipulative traders hide. Spoofing, layering, and wash trading are deliberately spread thin across venues specifically so no single venue's surveillance trips a threshold, and the same blind spot lets order-flow "toxicity" (adverse selection against market makers) go undetected until spreads have already widened and liquidity has already thinned.

That blind spot cascades downward into two further problems a broker actually has to act on. First, **mark-to-market accuracy**: a broker computing margin requirements off one fragmented, potentially toxic local price feed can miscall a margin deficit — either missing a real one (default risk) or falsely triggering one (forced liquidation that adds correlated sell pressure back into the same fragmented market, a known mechanism behind cascading liquidations). Second, **AML/manipulation detection**: FINRA's own guidance names layering, spoofing, wash trading, and coordinated cross-account activity as reportable patterns, but these are exactly the patterns that only become visible once flow is viewed *across* desks or institutions, not within one.

The fix — desks pooling order-flow signal — is also the thing no desk will ever agree to, because raw order flow reveals position size, client mix, and strategy to competitors, and centralizing it across firms is a competitive and regulatory non-starter. Making it worse: real-time trading, margin monitoring, and AML alerting all operate on a millisecond-to-second clock, while any privacy-preserving way of combining signal across parties (secure aggregation, differential privacy) adds communication and cryptographic overhead — federated learning's best-documented bottleneck. And any anonymization used to make cross-broker sharing acceptable has to stop short of true anonymity, because SEC Rule 613 (CAT) and MiFID II both require a persistent, non-anonymous order/client identifier for the compliance audit trail — a fully anonymized system would be unusable for exactly the regulators this system needs to satisfy.

**Core tension:** catching cross-broker fraud, mispricing, and margin risk requires combining signal across parties, but combining raw order flow is exactly what no broker will agree to — any privacy-preserving way of doing it adds latency in a domain that runs on milliseconds, and any anonymization used to make it acceptable can't be so strong that it breaks the paper trail regulators require.

---

## 2. Solution

A federated learning + agent system where each broker/desk trains a local order-flow model on its own data and pseudonymizes every order before it touches the shared layer. No broker's raw order or client data ever leaves that broker. Only model weights and pseudonymous (`hash_id`-tagged) flow signals sync to a central aggregator, which merges them (Flower `FedAvg` + secure aggregation) into one shared cross-venue model — giving every broker visibility into patterns that no single broker's data could reveal alone.

The design rests on two structural splits, which are the two insights the whole system is built around:

**Split 1 — Two-tier identity, not one anonymity layer:**
Each broker computes `hash_id = HMAC(broker_secret, real_order/client_ID)` before anything crosses the federation boundary. This is a *pseudonym*, not an anonymization — reversible only by the broker that generated it, holding a local vault mapping `hash_id → real CAT-Order-ID/FDID`. The shared federation and its agents only ever see `hash_id`. This satisfies both sides of the earlier tension at once: the shared model gets a stable identifier to detect cross-broker patterns against, and the compliance-mandated paper trail stays fully intact and reversible at the source, on demand, exactly as SEC/FINRA and MiFID II require.

**Split 2 — Real-time inference vs. periodic federated training:**
*Layer 1 (local, instant):* every order is scored against the broker's current local model the moment it arrives — no network call, no dependency on the federation, so trading-speed decisions never wait on federated-round speed.
*Layer 2 (cross-broker, communication-bound):* on a slower cadence, brokers synchronize model weights and pseudonymous flow signals so the shared model improves. This is where the real tradeoff lives: more privacy-preserving aggregation (noise, larger anonymity-set thresholds, mask reconstruction on dropout) makes each round slower and more expensive, and slower rounds mean the shared model goes stale faster against fast-evolving manipulation patterns.

**Three cooperating agents read the same shared signal for three different jobs:**

| Agent | Reads | Detects |
|---|---|---|
| OrderFlowAgent | Cross-venue flow imbalance, toxicity/VPIN score | Fragmentation-driven mispricing, adverse selection |
| MarginAgent | Same price signal + local margin book | Mark-to-market accuracy, margin-call cascades across brokers |
| AMLAgent | Same flow signal, keyed on `hash_id` | Spoofing, layering, wash trading, SAR candidates |

**The demo's core question, made visible and adjustable:** how much anonymity/privacy can you add to the shared layer before it either (a) breaks the compliance-required paper trail, or (b) makes the round too slow to be useful — while the real-time trading path, provably, never slows down at all.

---

## 3. Why this needs Flower + AWS + AMD + Arm (not just a script)

| Requirement | Why it rules out a simple centralized approach |
|---|---|
| Order flow/client data must never leave the broker | Centralizing it is a competitive and regulatory non-starter |
| Shared model must still improve from all brokers' signal | Requires real cross-node weight aggregation (Flower `FedAvg`, SecAgg+) |
| Compliance requires a reversible, non-anonymous ID | Requires a two-tier pseudonym design, not a one-shot anonymization hack |
| Fraud/margin detection must stay real-time per order | Requires an architecture that explicitly separates inference from training |
| Privacy vs. latency vs. model freshness is a genuine, tunable tradeoff | Needs an actual FL round-based system to demonstrate, not a static model |
| Edge nodes (many brokers) need cheap always-on compute | Arm Graviton price-performance fits a many-small-nodes topology |
| Aggregation + agent LLM inference needs real training throughput | AMD EPYC (aggregation hosts) + AMD Instinct (model training/agent inference) |

This mirrors a proven production pattern: Banking Circle uses Flower to train AML models across jurisdictions without moving data across borders (reported gains of 65% precision, 25% recall in initial testing), and J.P. Morgan's Kinexys unit ran a comparable federated fraud-detection proof-of-concept (Project AIKYA, with BNY, RBC, DeepTempo, and NVIDIA) showing cross-institutional fraud patterns invisible to any single institution become detectable once combined. Our project applies the same shape to equity brokers specifically, adding the pseudonym/compliance split and the real-time/training split as the added technical contribution, on Flower's newer Agent/SuperGrid layer rather than the FL core alone.

---

## 4. What we build (hackathon scope)

1. **Synthetic order-flow generator** — ~5 simulated brokers, each with a stream of fake orders (timestamp, size, price, side, ticker, venue), with injected fragmentation/toxicity patterns and a few cross-broker-coordinated fraud patterns (rapid cancels, size spikes, synchronized timing across "brokers")
2. **HMAC pseudonymization step** — each broker hashes its own order/client IDs before anything is sent to the shared layer; local vault (simple key-value store) keeps the real ID mapping, never transmitted
3. **Local order-flow/fraud model** — simple classifier (logistic regression) per broker, trained on that broker's own synthetic data
4. **ClientApp** — loads one broker's data, trains locally, returns weights + local flow stats tagged by `hash_id`
5. **ServerApp** — runs Flower's `FedAvg` across simulated brokers (Flower simulation mode on SuperGrid, no real network needed); tracks round duration and bytes transferred
6. **Three AgentApps** (OrderFlowAgent, MarginAgent, AMLAgent) — thin agent wrappers around the shared model's output, each producing a distinct decision/flag from the same signal
7. **Privacy/anonymity dial** — an adjustable control that, when increased, adds noise/larger anonymity-set thresholds to weight updates before aggregation (a simplified, honestly-framed stand-in for real SecAgg+/differential privacy) and simulates the resulting increase in round latency
8. **Compliance reveal demo** — a mock "regulator query" button that takes a flagged `hash_id` and shows it only resolves to a real identity at the originating broker's node, never at the federation layer
9. **Dashboard** — shows, live: (a) real-time order-scoring counter proving zero network wait on the inference path, (b) federated round progress and global model accuracy improving over rounds, (c) the privacy dial's effect on round overhead vs. model freshness, (d) the three agents' outputs (flow decision, margin flag, AML flag) side by side for the same order stream

---

## 5. Demo narrative (5:30pm slot)

1. **The problem, 30 seconds** — brokers can't share order flow, but fragmentation, margin cascades, and manipulation all span brokers; the standard fix is either "don't share" (miss cross-broker patterns) or "share everything" (competitive/regulatory dealbreaker, and breaks compliance if done via pure anonymization)
2. **Show the brokers** — 5 local order streams, visibly separate, each hashing its own IDs before anything leaves the node
3. **Show real-time scoring live** — orders scored instantly, a counter proving no network dependency
4. **Run a federated round live** — weights and pseudonymous flow signals sync, not raw order data; global model accuracy improves; OrderFlowAgent/MarginAgent/AMLAgent outputs update together
5. **Trigger the compliance reveal** — flag a `hash_id`, show it resolves to a real identity only at the originating broker, nowhere else in the system
6. **Turn the privacy dial up** — round overhead visibly increases, model improvement slows — the tradeoff, made honest and visual
7. **Close** — "the trading layer never slowed down, the compliance trail was never broken, and the tradeoff lives entirely in how fast the shared intelligence improves — and that's a dial the brokers can tune themselves"

---

## 6. Success criteria for the day

- Real `flwr run` executes end-to-end on synthetic data across simulated brokers, not a static mockup
- Dashboard makes the inference/training speed split, and the two-tier ID split, visually unambiguous — judges shouldn't need either explained twice
- Compliance reveal demo actually proves (not just asserts) that only the originating broker can de-anonymize a flagged `hash_id`
- Privacy dial produces a genuine, defensible tradeoff (even if simulated) rather than an arbitrary slider
- Judges can articulate, unprompted, why this needed Flower's federation/agent layer — and the AWS/AMD/Arm compute tiering — rather than a normal script

---

## 7. Open risks

- Real secure aggregation/differential privacy is out of scope for one day — must be clearly and honestly framed as a simulated stand-in, not implemented cryptography, when presenting to judges
- Local model choice — default to logistic regression if time is tight; simple, fast to train per round, easy to explain live
- Three agents (OrderFlow/Margin/AML) is ambitious for one day — scope to one fully working agent (OrderFlowAgent) plus stub outputs for the other two if time runs short, rather than three shallow implementations
- Provisioning real AWS/AMD/Arm instances (Graviton edge nodes, EPYC/Instinct aggregation hosts) is a stretch goal — Flower simulation mode on a single machine is an acceptable fallback if sponsor-hardware provisioning eats too much setup time
- Team composition unknown until team formation (10:45am) — scope to be doable by 2 people, with the three-agent split, compliance-reveal demo, and dashboard polish as stretch goals for a larger team
- Fraud/fragmentation pattern realism in synthetic data matters for the story landing — worth having the finance-background teammate design these patterns rather than defaulting to random noise
