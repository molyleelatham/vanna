import { FormEvent, useEffect, useMemo, useState } from "react";
import { assessOrder, getConnectivity, getDecisionStatus, getQuote, queueApproval, type Connectivity, type DecisionJob, type Quote } from "./api";
import { demoEvidence } from "./data/demo";
import type { PipelineResult, ProviderEvidence } from "./types";

const defaultOrder: PipelineResult["order_context"] = {
  pair: "EUR/USD",
  side: "BUY",
  size_bucket: "1m-5m",
  volatility: "high",
  available_providers: ["LP_A", "LP_B", "LP_C"],
};

const scenarios: Array<{ label: string; order: PipelineResult["order_context"] }> = [
  { label: "The Twist", order: defaultOrder },
  { label: "Clean Allow", order: { pair: "EUR/USD", side: "BUY", size_bucket: "<1m", volatility: "calm", available_providers: ["LP_B"] } },
  { label: "Throttle", order: { pair: "EUR/USD", side: "BUY", size_bucket: "1m-5m", volatility: "normal", available_providers: ["LP_B", "LP_C"] } },
  { label: "Stress Escalation", order: { pair: "GBP/JPY", side: "SELL", size_bucket: ">10m", volatility: "high", available_providers: ["LP_A", "LP_B", "LP_C"] } },
  { label: "Trust Check", order: { pair: "EUR/USD", side: "SELL", size_bucket: "5m-10m", volatility: "normal", available_providers: ["LP_A"] } },
];

const demoIdentity = {
  client: "Northstar Training Desk",
  uti: "SIM-UTI-2026-000184",
};

const technicalEvidence = [
  {
    title: "Collaboration changes the answer",
    proof: "60% → 11%",
    detail: "A desk-0-only model estimates LP_C fills at roughly 60%. The five-desk federated ensemble measures roughly 11%, preventing a materially wrong route.",
  },
  {
    title: "Model evidence is inspectable",
    proof: "23.64 gain",
    detail: "High-volatility is the strongest federated XGBoost feature. LP × volatility interactions are also retained, rather than hidden behind an LLM explanation.",
  },
  {
    title: "Every training run is auditable",
    proof: "3 checkpoints",
    detail: "The federation stores per-round model checkpoints, a training manifest, feature importance, final model digest, and the approved evidence artifact.",
  },
  {
    title: "Live tools are bounded and honest",
    proof: "6 tools / 10 calls",
    detail: "Market, flow, history, risk, surveillance, and federation connectors have a hard call budget. Unavailable sources are labelled unavailable, never silently invented.",
  },
  {
    title: "Resilience is designed in",
    proof: "Local fallback",
    detail: "No model narration, no connector, or no SuperGrid does not brick the demo: deterministic typed assessment and the last approved artifact remain available.",
  },
  {
    title: "Oversight is code, not copy",
    proof: "5 outcomes",
    detail: "Governance can allow, reduce size, use local fallback, require human review, or suppress collective output. Execution and blacklisting are unrepresentable.",
  },
];

const stressMockRun = [
  ["00:00", "SuperGrid request accepted", "Federation @molyleela/Vanna"],
  ["00:04", "Round 1 / 3", "5 of 5 SuperNodes sampled · no raw records shared"],
  ["00:10", "Round 2 / 3", "FedXgbBagging aggregate checkpoint saved"],
  ["00:16", "Round 3 / 3", "5 of 5 SuperNodes completed · 0 failures"],
  ["00:18", "Evidence approved", "provider_evidence.json exported to the AgentApp boundary"],
];

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function providerReason(provider: ProviderEvidence) {
  if (provider.provider === "LP_A") {
    return `The best displayed benefit (${provider.displayed_price_benefit_bps.toFixed(2)} bps) is outweighed by a ${percent(provider.fill_probability)} fill estimate, ${percent(provider.rejection_probability)} rejection estimate, and elevated last-look signal.`;
  }
  if (provider.provider === "LP_B") {
    return `Strong ${percent(provider.fill_probability)} fill estimate, lower ${percent(provider.rejection_probability)} rejection estimate, ${provider.expected_slippage_bps.toFixed(2)} bps expected slippage, and ${provider.expected_latency_ms.toFixed(1)} ms latency support executable value.`;
  }
  return `Low ${percent(provider.fill_probability)} fill estimate and ${percent(provider.rejection_probability)} rejection estimate dominate its displayed-price benefit. It remains visible for review, not automatically excluded.`;
}

function App() {
  const [order, setOrder] = useState(defaultOrder);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [job, setJob] = useState<DecisionJob | null>(null);
  const [connectivity, setConnectivity] = useState<Connectivity | null>(null);
  const [showSecAgg, setShowSecAgg] = useState(false);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [loadingDecision, setLoadingDecision] = useState(false);
  const [queueStatus, setQueueStatus] = useState("");
  const [error, setError] = useState("");
  const [activeScenario, setActiveScenario] = useState("The Twist");

  const providers = useMemo(
    () => [...demoEvidence.providers].sort((a, b) => b.fill_probability - a.fill_probability),
    [],
  );

  const refreshQuote = async () => {
    setLoadingQuote(true);
    try {
      setQuote(await getQuote(order.pair));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not retrieve quote.");
    } finally {
      setLoadingQuote(false);
    }
  };

  useEffect(() => {
    const refreshLiveQuote = () => {
      getQuote(order.pair).then(setQuote).catch(() => setQuote(null));
    };
    refreshLiveQuote();
    const interval = window.setInterval(refreshLiveQuote, 15_000);
    return () => window.clearInterval(interval);
  }, [order.pair]);
  useEffect(() => {
    getConnectivity().then(setConnectivity).catch(() => setConnectivity(null));
  }, []);

  const submitOrder = async (event: FormEvent) => {
    event.preventDefault();
    setLoadingDecision(true);
    setQueueStatus("");
    try {
      const submitted = await assessOrder(order);
      setJob(submitted);
      setError("");
      void pollDecision(submitted.job_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not assess order.");
    } finally {
      setLoadingDecision(false);
    }
  };

  const sendForApproval = async () => {
    if (!job || job.status !== "completed") return;
    try {
      const response = await queueApproval(job.job_id);
      setQueueStatus(response.status.replaceAll("_", " "));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not queue approval.");
    }
  };

  const pollDecision = async (jobId: string) => {
    try {
      const next = await getDecisionStatus(jobId);
      setJob(next);
      if (next.status === "queued" || next.status === "running") {
        window.setTimeout(() => void pollDecision(jobId), 1000);
        return;
      }
      setLoadingDecision(false);
      if (next.status === "failed") setError(next.error ?? "Flower AgentApp assessment unavailable.");
    } catch (reason) {
      setLoadingDecision(false);
      setError(reason instanceof Error ? reason.message : "Could not read Flower job status.");
    }
  };

  const result = job?.result;
  const recommendation = result?.vanna_recommendation;
  const modelComparison = Array.isArray(result?.model_comparison) ? result.model_comparison : null;
  const jobActive = job?.status === "queued" || job?.status === "running";
  const selectScenario = (next: PipelineResult["order_context"], label: string) => {
    setOrder(next);
    setActiveScenario(label);
    setJob(null);
    setQueueStatus("");
    setError("");
  };

  return (
    <main>
      <header className="site-header terminal-header">
        <div><p className="eyebrow">Vanna / federated execution intelligence</p><h1>Vanna is a trade-assessment tool built on federated learning.</h1><p className="terminal-subtitle">Five competing FX desks learn together from their own execution histories — but raw trades never leave the desk.</p><div className="fab-badges"><span>FAB · vanna-federation</span><b>→ approved evidence →</b><span>FAB · vanna-agent</span></div></div>
        <div className="header-status"><button className="feature-button" onClick={() => setShowSecAgg(!showSecAgg)} aria-expanded={showSecAgg}>SecAgg+ · opt-in</button><span className="pill">Advisory only</span><span>Automatic execution disabled</span></div>
      </header>

      {showSecAgg && <section className="feature-drawer" aria-label="SecAgg+ secure aggregation feature">
        <div><p className="eyebrow">Federation feature</p><h2>SecAgg+ secure aggregation</h2><p>When enabled for a separate federation run, each desk masks its logistic-model update. The server reconstructs only the weighted average across the five-desk cohort.</p></div>
        <div className="feature-state"><strong>Not active in this snapshot</strong><p>This terminal is reading the default approved XGBoost evidence artifact. SecAgg+ is an explicit background FedAvg run, never an order-ticket setting.</p><code>secure-aggregation=true</code></div>
      </section>}

      <section className="identity-bar" aria-label="Demo trace identifiers">
        <div><span>Demo client</span><strong>{demoIdentity.client}</strong><small>Fictional display label — never sent to Flower</small></div>
        <div><span>Trace token</span><strong>{demoIdentity.uti}</strong><small>Simulated only — not a real UTI or order record</small></div>
        <div><span>Data contract</span><strong>Bucketed order context only</strong><small>No client IDs, accounts, raw orders, positions, or live intent</small></div>
      </section>

      <section className="quote-strip" aria-live="polite">
        <div><p className="eyebrow">Market data</p><strong>{quote?.pair ?? order.pair}</strong></div>
        <div><span>Bid</span><strong>{quote ? quote.bid.toFixed(5) : "—"}</strong></div>
        <div><span>Ask</span><strong>{quote ? quote.ask.toFixed(5) : "—"}</strong></div>
        <div><span>Source</span><strong>{quote?.fallback ? "Local fallback" : quote?.source ?? "Loading"}</strong></div>
        <button className="accent-button" onClick={refreshQuote} disabled={loadingQuote}>{loadingQuote ? "Refreshing…" : "Refresh quote"}</button>
      </section>

      <div className="terminal-grid">
        <section className="ticket-panel" aria-labelledby="ticket-title">
          <p className="eyebrow">Order ticket</p>
          <h2 id="ticket-title">Assess a proposed trade.</h2>
          <p className="muted">Only bucketed context is evaluated locally. No broker or OMS order is created.</p>
          <div className="scenario-row" aria-label="Demo scenarios">
            {scenarios.map((scenario) => <button type="button" key={scenario.label} onClick={() => selectScenario(scenario.order, scenario.label)}>{scenario.label}</button>)}
          </div>
          <form onSubmit={submitOrder}>
            <label>Pair
              <select value={order.pair} onChange={(event) => setOrder({ ...order, pair: event.target.value })}>
                <option>EUR/USD</option><option>GBP/USD</option><option>GBP/JPY</option><option>USD/JPY</option>
              </select>
              <small>The currency pair being assessed.</small>
            </label>
            <div className="form-row">
              <label>Side<select value={order.side} onChange={(event) => setOrder({ ...order, side: event.target.value as "BUY" | "SELL" })}><option>BUY</option><option>SELL</option></select><small>Buy or sell direction.</small></label>
              <label>Size bucket<select value={order.size_bucket} onChange={(event) => setOrder({ ...order, size_bucket: event.target.value as PipelineResult["order_context"]["size_bucket"] })}><option>&lt;1m</option><option>1m-5m</option><option>5m-10m</option><option>&gt;10m</option></select><small>Range only; exact notional is never shared.</small></label>
            </div>
            <label>Volatility<select value={order.volatility} onChange={(event) => setOrder({ ...order, volatility: event.target.value as PipelineResult["order_context"]["volatility"] })}><option>calm</option><option>normal</option><option>high</option></select><small>Current market-movement regime; it changes execution risk.</small></label>
            <fieldset><legend>Available liquidity providers</legend><small>Which approved providers may be compared; these are provider labels, not client identities.</small>{["LP_A", "LP_B", "LP_C"].map((provider) => <label className="checkbox-label" key={provider}><input type="checkbox" checked={order.available_providers.includes(provider)} onChange={() => setOrder({ ...order, available_providers: order.available_providers.includes(provider) ? order.available_providers.filter((item) => item !== provider) : [...order.available_providers, provider] })} />{provider}</label>)}</fieldset>
            <button className="accent-button full-button" disabled={loadingDecision || !order.available_providers.length}>{loadingDecision ? "Assessing…" : "Assess order"}</button>
          </form>
        </section>

        <section className="decision-panel" aria-labelledby="decision-title">
          <p className="eyebrow">Governed decision</p>
          <h2 id="decision-title">{recommendation ? `${recommendation.provider} recommended` : job ? `SuperLink AgentApp ${job.status}` : "Awaiting order assessment"}</h2>
          <div className="provider-rationale" aria-label="Provider trade-offs">
            {demoEvidence.providers.map((provider) => <article key={provider.provider} className={recommendation?.provider === provider.provider ? "chosen-provider" : ""}><div><h3>{provider.provider}{recommendation?.provider === provider.provider && <span>Recommended</span>}</h3><strong>{percent(provider.fill_probability)} expected fill</strong></div><p>{providerReason(provider)}</p><small>Slippage {provider.expected_slippage_bps.toFixed(2)} bps · latency {provider.expected_latency_ms.toFixed(1)} ms · asymmetry {provider.rejection_asymmetry.toFixed(2)}</small></article>)}
          </div>
          {recommendation ? <><dl className="decision-stats"><div><dt>Expected cost</dt><dd>{recommendation.expected_cost_bps.toFixed(2)} bps</dd></div><div><dt>Confidence</dt><dd>{recommendation.confidence}</dd></div><div><dt>Governance</dt><dd className="warning">{result.governance.action.replaceAll("_", " ")}</dd></div></dl><p>{recommendation.reason}</p><div className="agent-reasoning"><article><h3>Last look</h3><p>{result.last_look_signal?.explanation ?? "Assessment returned in the agent handoff trace."}</p></article><article><h3>Counterparty reliability</h3><p>{result.counterparty_risk ? `${result.counterparty_risk.provider}: reliability ${result.counterparty_risk.reliability_score.toFixed(2)}; route posture ${result.counterparty_risk.route_posture}.` : "Assessment returned in the agent handoff trace."}</p></article><article><h3>Margin control</h3><p>{result.margin ? `${result.margin.pressure} pressure; recommended size multiplier ${result.margin.recommended_size_multiplier.toFixed(2)}.` : "Assessment returned in the agent handoff trace."}</p></article><article><h3>Surveillance</h3><p>{result.manipulation ? `${result.manipulation.provider}: ${result.manipulation.signal} signal, anomaly score ${result.manipulation.anomaly_score.toFixed(2)}.` : "Assessment returned in the agent handoff trace."}</p></article><article className="governance-reasons"><h3>Why governance decided this</h3><ul>{result.governance.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></article></div><button className="approval-button" onClick={sendForApproval}>Send to approval queue</button><p className="muted">This creates a local, non-executable approval record only.</p>{queueStatus && <p className="queue-status" role="status">{queueStatus}</p>}</> : <p>{job && (job.status === "queued" || job.status === "running") ? "A real Flower AgentApp run is in progress on local SuperLink. Waiting for its structured decision event." : "Submit a bucketed ticket to start a real local-SuperLink Flower AgentApp run."}</p>}
        </section>
      </div>
      {error && <p className="error page-error" role="alert">{error}</p>}

      <section className="section execution-quality">
        <div className="section-heading"><div><p className="eyebrow">Execution quality</p><h2>Displayed price is not execution quality.</h2></div><p className="muted">Approved federation artifact · 5-desk cohort</p></div>
        <p className="comparison-intro">A quote can look attractive before trading, but execution quality asks what happens when the trade is actually attempted: does it fill, at what price, how quickly, and does the provider reject it when the market moves?</p>
        <div className="table-wrap"><table><thead><tr><th>Provider<small>Which liquidity provider is being compared</small></th><th>Fill<small>Chance the proposed trade completes</small></th><th>Displayed benefit<small>The price advantage shown before attempting the trade</small></th><th>Slippage<small>How much worse the final price may become</small></th><th>Latency<small>Time taken to complete or reject the request</small></th><th>Last-look signal<small>Whether rejection is unusually linked to adverse market moves</small></th></tr></thead><tbody>{providers.map((provider: ProviderEvidence) => <tr key={provider.provider} className={recommendation?.provider === provider.provider ? "selected" : ""}><th scope="row">{provider.provider}</th><td>{percent(provider.fill_probability)}</td><td>{provider.displayed_price_benefit_bps.toFixed(2)} bps</td><td>{provider.expected_slippage_bps.toFixed(2)} bps</td><td>{provider.expected_latency_ms.toFixed(1)} ms</td><td>{provider.rejection_asymmetry.toFixed(2)}</td></tr>)}</tbody></table></div>
        <p className="note"><strong>What is “last look”?</strong> In some FX markets, a provider can briefly check a trade after quoting it and reject it before completion. Vanna treats a pattern of conditional rejection as a review signal only — it is not proof of misconduct and never triggers an automatic blacklist.</p>
      </section>

      <section className="section split-section">
        <div><p className="eyebrow">Agent and Flower trace</p><h2>Every activation is explicit.</h2><p>Each assessment starts a local SuperLink Flower AgentApp run. The UI polls its request-scoped structured decision event; it never substitutes a direct local pipeline result.</p></div>
        <ul className="safety-list"><li>Public quote <strong>{quote?.fallback ? "Fallback" : quote ? "Active" : "Loading"}</strong></li><li>Federated evidence <strong>Loaded</strong></li><li>Agent assessment <strong>{job?.status ?? "Waiting"}</strong></li><li>SuperLink AgentApp <strong>{job?.status ?? "Ready"}</strong></li><li>Broker execution <strong>Disabled</strong></li></ul>
      </section>

      <section className="section" aria-labelledby="behind-scenes-title">
        <div className="section-heading">
          <div><p className="eyebrow">Behind the scenes</p><h2 id="behind-scenes-title">How this ticket becomes a governed decision.</h2></div>
          <p className="muted">Technical trace, explained without trading jargon.</p>
        </div>
        <div className="connectivity-grid">
          <article>
            <span className={`connection-dot ${connectivity ? "online" : "offline"}`} aria-hidden="true" />
            <h3>1. Browser to local gateway</h3>
            <p>The order ticket talks only to the local gateway on port 8010. It accepts a small, validated set of fields rather than account or client data.</p>
            <strong>{connectivity?.gateway ?? "checking connection"}</strong>
          </article>
          <article>
            <span className={`connection-dot ${connectivity?.superlink === "reachable" ? "online" : "offline"}`} aria-hidden="true" />
            <h3>2. Gateway to Flower SuperLink</h3>
            <p>The gateway starts a real Flower job. SuperLink schedules the Vanna AgentApp and returns one request-scoped result to the terminal.</p>
            <strong>{connectivity?.superlink === "reachable" ? `connected · ${connectivity.superlink_endpoint}` : "not reachable"}</strong>
          </article>
          <article>
            <span className={`connection-dot ${job?.status === "completed" ? "online" : "offline"}`} aria-hidden="true" />
            <h3>3. AgentApp handoff chain</h3>
            <p>Six specialist checks run in sequence: execution value, last look, reliability, margin, surveillance, then governance. The model narrates; typed code makes the decision.</p>
            <strong>{job ? `job ${job.status}` : "waiting for a ticket"}</strong>
          </article>
          <article>
            <span className="connection-dot online" aria-hidden="true" />
            <h3>4. Privacy and audit boundary</h3>
            <p>Agents read approved aggregate provider evidence. Raw orders, identities, positions, and live intent do not cross the federation boundary.</p>
            <strong>{connectivity?.data_boundary ?? "approved aggregate evidence only"}</strong>
          </article>
        </div>
        <div className="handoff-flow" aria-label="Technical request flow">
          <span>Ticket</span><b>→</b><span>Gateway</span><b>→</b><span>SuperLink</span><b>→</b><span>Vanna AgentApp</span><b>→</b><span>Governance</span><b>→</b><span>Human approval</span>
        </div>
        <p className="note"><strong>What is deliberately not connected:</strong> the approval queue is local-only. There is no broker, OMS, automatic execution, automatic blacklisting, or collective provider instruction behind this screen.</p>
      </section>

      <section className="section architecture-map" aria-labelledby="architecture-title">
        <div className="section-heading">
          <div><p className="eyebrow">Flower architecture</p><h2 id="architecture-title">Where the data moves.</h2></div>
          <p className="muted">{jobActive ? "Active request path is highlighted in dark." : "Start an assessment to highlight the live request path."}</p>
        </div>
        <p className="comparison-intro">Two independent Flower FABs collaborate through one approved evidence artifact. The federation updates learning in the background; the terminal asks the AgentApp for a governed explanation without exposing desk records.</p>
        <div className="architecture-lane">
          <p>Background federation / five private desks</p>
          <div className="diagram-row federation-row">
            <div className="diagram-node local desk-cluster"><strong>Five private desks</strong><div className="desk-mini-row"><span>Desk A</span><span>Desk B</span><span>Desk C</span><span>Desk D</span><span>Desk E</span></div><small>Private histories stay local</small></div>
            <i>→</i>
            <div className="diagram-node"><strong>5 ClientApps</strong><small>vanna-federation FAB</small></div>
            <i>→</i>
            <div className="diagram-node"><strong>SuperLink + SuperExec</strong><small>Schedules background federation work</small></div>
            <i>→</i>
            <div className="diagram-node"><strong>ServerApp</strong><small>FedXgbBagging or opt-in SecAgg+</small></div>
            <i>→</i>
            <div className="diagram-node artifact"><strong>Approved evidence</strong><small>Aggregate metrics only</small></div>
          </div>
          <div className="federation-highlight">
            <div><p className="eyebrow">Default federation mode</p><h3>FedXgbBagging</h3><p>Each desk trains its own small XGBoost tree model on private history. Flower combines those learned trees into a stronger shared model without moving the underlying trade records.</p></div>
            <div><strong>Why it matters</strong><p>It can capture non-linear patterns—for example, a provider behaving differently when volatility is high—while the raw desk data stays local.</p><small>SecAgg+ is the separate opt-in FedAvg logistic mode when masked-update aggregation is required.</small></div>
          </div>
          <div className="supergrid-lane">
            <span className="diagram-node supergrid"><strong>SuperGrid · @molyleela/Vanna</strong><small>Remote Flower deployment federation</small></span>
            <b>→</b>
            <span className="diagram-node"><strong>Remote SuperExec</strong><small>Runs the FAB workloads remotely</small></span>
            <b>→</b>
            <span className="diagram-node"><strong>5 authenticated SuperNodes</strong><small>One private desk partition per node</small></span>
            <b>→</b>
            <span className="diagram-node"><strong>Verified runs</strong><small>Federation: 3 rounds, 5/5 nodes, 0 failures · AgentApp: full chain</small></span>
          </div>
          <p className="remote-note">Remote SuperGrid is the deployment proof. This browser does not poll or control it; the current interactive request stays on local SuperLink for a reliable live demo.</p>
        </div>
        <div className="architecture-lane">
          <p>Interactive governed assessment</p>
          <div className="diagram-row agent-row">
            <div className={`diagram-node ${jobActive ? "active" : ""}`}><strong>Browser terminal</strong><small>Bucketed ticket only</small></div>
            <i className={jobActive ? "active-arrow" : ""}>→</i>
            <div className={`diagram-node ${jobActive ? "active" : ""}`}><strong>Local gateway</strong><small>Validates and starts Flower run</small></div>
            <i className={jobActive ? "active-arrow" : ""}>→</i>
            <div className={`diagram-node ${jobActive ? "active" : ""}`}><strong>SuperLink</strong><small>Local runtime at :9093</small></div>
            <i className={jobActive ? "active-arrow" : ""}>→</i>
            <div className={`diagram-node ${jobActive ? "active" : ""}`}><strong>SuperExec</strong><small>Launches short-lived AgentApp</small></div>
            <i className={jobActive ? "active-arrow" : ""}>→</i>
            <div className={`diagram-node ${jobActive ? "active" : ""}`}><strong>vanna-agent FAB</strong><small>Six typed checks + governance</small></div>
          </div>
          <div className="diagram-return"><span className="diagram-node artifact"><strong>Approved evidence</strong><small>Read-only local artifact</small></span><b>→</b><span className={`diagram-node ${jobActive ? "active" : ""}`}><strong>Structured decision event</strong><small>Result, trace, audit metadata</small></span><b>→</b><span className="diagram-node local"><strong>Human approval</strong><small>No broker or OMS connection</small></span></div>
        </div>
        <p className="note"><strong>Privacy guardrail:</strong> the diagram never represents raw orders moving between desks, SuperNodes, the server, or the browser. Only model updates and approved aggregate evidence move through the federated path.</p>
      </section>

      <section className="section why-flower" aria-labelledby="why-flower-title">
        <div className="section-heading">
          <div><p className="eyebrow">Why Flower</p><h2 id="why-flower-title">Collaboration, federation, and security in one platform.</h2></div>
          <p className="muted">Flower is the operating layer, not a logo added after the model.</p>
        </div>
        <div className="why-flower-grid">
          <article><span>01</span><h3>Collaboration</h3><p>Flower runs the shared infrastructure for five isolated desks and the six-agent Vanna chain. Each agent contributes one typed, reviewable decision input instead of hiding everything in one large prompt.</p><small>What it means: independent participants can contribute knowledge without becoming one shared database.</small></article>
          <article><span>02</span><h3>Federation</h3><p>Each desk trains locally through a Flower ClientApp. The ServerApp combines learning and exports only approved provider evidence for the AgentApp to use later.</p><small>What it means: learn from patterns across desks while raw trade records stay at their original desk.</small></article>
          <article><span>03</span><h3>Security and control</h3><p>Vanna validates every shared payload, uses bucketed inputs, and re-validates evidence before agents read it. Flower also provides the opt-in SecAgg+ workflow for masked FedAvg updates.</p><small>Important: SecAgg+ applies only to the separate logistic FedAvg mode. Default XGBoost bagging does not mask individual model updates, and differential privacy is not implemented.</small></article>
        </div>
        <p className="note"><strong>Why this combination matters:</strong> a local-only system cannot see the cross-desk pattern; a centralised system would require sharing sensitive records. Flower provides the distributed execution substrate, while Vanna adds strict privacy contracts, deterministic scoring, and human governance.</p>
      </section>

      <section className="section live-feed" aria-labelledby="feed-title">
        <div className="section-heading">
          <div><p className="eyebrow">Live activity</p><h2 id="feed-title">System feed</h2></div>
          <p className="muted">Public quote refreshes every 15 seconds; Flower events update with each assessment.</p>
        </div>
        <ol>
          <li><time>{quote ? new Date(quote.timestamp).toLocaleTimeString() : "—"}</time><div><strong>Market quote</strong><p>{quote ? `${quote.pair} bid ${quote.bid.toFixed(5)} / ask ${quote.ask.toFixed(5)} from ${quote.fallback ? "the labelled local fallback" : "Alpha Vantage"}` : "Awaiting public quote source."}</p></div></li>
          <li><time>READY</time><div><strong>vanna-federation FAB</strong><p>Five-desk approved evidence artifact is loaded. Shared counters: 0 raw records and 0 client identities.</p></div></li>
          <li><time>{job?.status?.toUpperCase() ?? "READY"}</time><div><strong>vanna-agent FAB</strong><p>{job ? `SuperLink job ${job.job_id.slice(0, 8)} is ${job.status}.` : "Ready to receive a validated, bucketed order ticket through local SuperLink."}</p></div></li>
          <li><time>LOCAL</time><div><strong>Audit guardrail</strong><p>{queueStatus ? `Approval record is ${queueStatus.toLowerCase()}.` : "No approval record exists until an operator explicitly queues a completed governed decision."}</p></div></li>
        </ol>
      </section>

      {activeScenario === "Stress Escalation" && <section className="section mock-run-feed" aria-labelledby="mock-run-title">
        <div className="section-heading">
          <div><p className="eyebrow">Stress Escalation companion view</p><h2 id="mock-run-title">Simulated SuperGrid federation run</h2></div>
          <span className="mock-badge">Mock log · not a live remote connection</span>
        </div>
        <p className="comparison-intro">This shows the kind of federation activity that produced the approved evidence used by the stress scenario. It is intentionally simulated for the browser demo; live online logs remain in the authenticated Flower run stream.</p>
        <ol>
          {stressMockRun.map(([time, event, detail]) => <li key={time}><time>{time}</time><div><strong>{event}</strong><p>{detail}</p></div></li>)}
        </ol>
        <p className="note"><strong>What this demonstrates:</strong> five private desks contribute learning updates, the server aggregates approved results, and only the resulting provider evidence crosses into the AgentApp. The stress ticket itself still runs through local SuperLink.</p>
      </section>}

      <section className="section evidence-lab" aria-labelledby="evidence-lab-title">
        <div className="section-heading">
          <div><p className="eyebrow">Technical evidence</p><h2 id="evidence-lab-title">Verification</h2></div>
          <p className="muted">Measured artifacts and controls, not marketing claims.</p>
        </div>
        <div className="technical-grid">
          {technicalEvidence.map((item) => <article key={item.title}><span>{item.proof}</span><h3>{item.title}</h3><p>{item.detail}</p></article>)}
        </div>
        <div className="evidence-detail-grid">
          <article><p className="eyebrow">Flower infrastructure</p><h3>Two real FABs, one typed boundary</h3><p><strong>vanna-federation</strong> runs five desk partitions with a ServerApp/ClientApp pair. <strong>vanna-agent</strong> runs the six-agent chain. The approved evidence JSON is the only bridge; a Flower FAB cannot combine both application types.</p><small>Verified SuperGrid: 5/5 nodes, 3 rounds, 0 failures.</small></article>
          <article><p className="eyebrow">Feature attribution</p><h3>Why the model changes its view</h3><p>Top federated signals: high volatility <strong>23.64</strong>, LP_A high-volatility interaction <strong>14.47</strong>, and LP_C high-volatility interaction <strong>8.46</strong> gain. This makes the last-look pattern explainable.</p><small>Read from the generated feature-importance artifact.</small></article>
          <article><p className="eyebrow">Governance controls</p><h3>Independent checks can stop a recommendation</h3><p>Minimum cohort, evidence freshness, synchronized-routing concentration, rare-participant queries, margin pressure, surveillance, and last-look asymmetry each escalate independently.</p><small>Last-look is a review signal, never a misconduct finding.</small></article>
          <article><p className="eyebrow">Security mode choice</p><h3>Transparent trade-off, not a checkbox</h3><p>Default FedXgbBagging captures nonlinear behavior. Opt-in SecAgg+ masks desk updates but uses a transparent logistic FedAvg model because secure summation cannot merge XGBoost trees.</p><small>Both export the same approved evidence schema.</small></article>
        </div>
      </section>

      <section className="section comparison-panel" aria-labelledby="comparison-title">
        <div className="section-heading">
          <div><p className="eyebrow">Collaboration proof</p><h2 id="comparison-title">One desk versus five desks.</h2></div>
          <p className="muted">Populated from the completed AgentApp run.</p>
        </div>
        <p className="comparison-intro">This is the simple test for whether sharing approved learning helps: the local model sees one desk’s narrow history, while the federated model learns from five isolated desks without pooling their raw orders.</p>
        {modelComparison ? <div className="table-wrap"><table><thead><tr><th>Provider<br /><small>Which price source is being compared</small></th><th>One-desk estimate<br /><small>What one desk expects to fill</small></th><th>Five-desk estimate<br /><small>What the federated model expects</small></th><th>One-desk test error<br /><small>Lower means more accurate on unseen examples</small></th><th>Five-desk test error<br /><small>Same check after learning across desks</small></th><th>Agreement<br /><small>Whether both models tell the same story</small></th></tr></thead><tbody>{modelComparison.map((comparison) => <tr key={comparison.provider}><th scope="row">{comparison.provider}</th><td>{percent(comparison.local_only_fill_prob)}</td><td>{percent(comparison.federated_fill_prob)}</td><td>{comparison.local_only_logloss_held_out.toFixed(3)}</td><td>{comparison.federated_logloss_held_out.toFixed(3)}</td><td>{comparison.model_agreement ? "Yes" : "No — investigate"}</td></tr>)}</tbody></table></div> : <div className="comparison-empty"><strong>Run an assessment to load the measured comparison.</strong><p>The table comes from the real local-SuperLink AgentApp result so it never presents a stale local estimate as live evidence.</p></div>}
        <p className="note"><strong>How to read it:</strong> fill estimate is the expected chance a provider completes a trade. Test error checks the estimate against examples the model did not train on; lower is better. A disagreement is valuable because it shows where collaboration changes a desk’s local conclusion.</p>
      </section>

      {result && <section className="section"><p className="eyebrow">Typed handoffs</p><h2>Agent contribution trace</h2><ol className="agent-chain">{result.contributions.map((contribution, index) => <li key={contribution.agent}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{contribution.agent}</h3><p>{contribution.summary}</p></div></li>)}</ol></section>}
    </main>
  );
}

export default App;
