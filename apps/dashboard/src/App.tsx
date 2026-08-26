import { FormEvent, useEffect, useMemo, useState } from "react";
import { assessOrder, getDecisionStatus, getQuote, queueApproval, type DecisionJob, type Quote } from "./api";
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

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function App() {
  const [order, setOrder] = useState(defaultOrder);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [job, setJob] = useState<DecisionJob | null>(null);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [loadingDecision, setLoadingDecision] = useState(false);
  const [queueStatus, setQueueStatus] = useState("");
  const [error, setError] = useState("");

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

  useEffect(() => { void refreshQuote(); }, []); // Initial terminal quote.

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
  const selectScenario = (next: PipelineResult["order_context"]) => {
    setOrder(next);
    setJob(null);
    setQueueStatus("");
    setError("");
  };

  return (
    <main>
      <header className="site-header terminal-header">
        <div><p className="eyebrow">Vanna / federated execution intelligence</p><h1>Execution terminal</h1></div>
        <div className="header-status"><span className="pill">Advisory only</span><span>Automatic execution disabled</span></div>
      </header>

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
            {scenarios.map((scenario) => <button type="button" key={scenario.label} onClick={() => selectScenario(scenario.order)}>{scenario.label}</button>)}
          </div>
          <form onSubmit={submitOrder}>
            <label>Pair
              <select value={order.pair} onChange={(event) => setOrder({ ...order, pair: event.target.value })}>
                <option>EUR/USD</option><option>GBP/USD</option><option>GBP/JPY</option><option>USD/JPY</option>
              </select>
            </label>
            <div className="form-row">
              <label>Side<select value={order.side} onChange={(event) => setOrder({ ...order, side: event.target.value as "BUY" | "SELL" })}><option>BUY</option><option>SELL</option></select></label>
              <label>Size bucket<select value={order.size_bucket} onChange={(event) => setOrder({ ...order, size_bucket: event.target.value as PipelineResult["order_context"]["size_bucket"] })}><option>&lt;1m</option><option>1m-5m</option><option>5m-10m</option><option>&gt;10m</option></select></label>
            </div>
            <label>Volatility<select value={order.volatility} onChange={(event) => setOrder({ ...order, volatility: event.target.value as PipelineResult["order_context"]["volatility"] })}><option>calm</option><option>normal</option><option>high</option></select></label>
            <fieldset><legend>Available liquidity providers</legend>{["LP_A", "LP_B", "LP_C"].map((provider) => <label className="checkbox-label" key={provider}><input type="checkbox" checked={order.available_providers.includes(provider)} onChange={() => setOrder({ ...order, available_providers: order.available_providers.includes(provider) ? order.available_providers.filter((item) => item !== provider) : [...order.available_providers, provider] })} />{provider}</label>)}</fieldset>
            <button className="accent-button full-button" disabled={loadingDecision || !order.available_providers.length}>{loadingDecision ? "Assessing…" : "Assess order"}</button>
          </form>
        </section>

        <section className="decision-panel" aria-labelledby="decision-title">
          <p className="eyebrow">Governed decision</p>
          <h2 id="decision-title">{recommendation ? `${recommendation.provider} recommended` : job ? `SuperLink AgentApp ${job.status}` : "Awaiting order assessment"}</h2>
          {recommendation ? <><dl className="decision-stats"><div><dt>Expected cost</dt><dd>{recommendation.expected_cost_bps.toFixed(2)} bps</dd></div><div><dt>Confidence</dt><dd>{recommendation.confidence}</dd></div><div><dt>Governance</dt><dd className="warning">{result.governance.action.replaceAll("_", " ")}</dd></div></dl><p>{recommendation.reason}</p><button className="approval-button" onClick={sendForApproval}>Send to approval queue</button><p className="muted">This creates a local, non-executable approval record only.</p>{queueStatus && <p className="queue-status" role="status">{queueStatus}</p>}</> : <p>{job && (job.status === "queued" || job.status === "running") ? "A real Flower AgentApp run is in progress on local SuperLink. Waiting for its structured decision event." : "Submit a bucketed ticket to start a real local-SuperLink Flower AgentApp run."}</p>}
        </section>
      </div>
      {error && <p className="error page-error" role="alert">{error}</p>}

      <section className="section">
        <div className="section-heading"><div><p className="eyebrow">Execution quality</p><h2>Displayed price is not execution quality.</h2></div><p className="muted">Approved federation artifact · 5-desk cohort</p></div>
        <div className="table-wrap"><table><thead><tr><th>Provider</th><th>Fill</th><th>Displayed benefit</th><th>Slippage</th><th>Latency</th><th>Last-look signal</th></tr></thead><tbody>{providers.map((provider: ProviderEvidence) => <tr key={provider.provider} className={recommendation?.provider === provider.provider ? "selected" : ""}><th scope="row">{provider.provider}</th><td>{percent(provider.fill_probability)}</td><td>{provider.displayed_price_benefit_bps.toFixed(2)} bps</td><td>{provider.expected_slippage_bps.toFixed(2)} bps</td><td>{provider.expected_latency_ms.toFixed(1)} ms</td><td>{provider.rejection_asymmetry.toFixed(2)}</td></tr>)}</tbody></table></div>
      </section>

      <section className="section split-section">
        <div><p className="eyebrow">Agent and Flower trace</p><h2>Every activation is explicit.</h2><p>Each assessment starts a local SuperLink Flower AgentApp run. The UI polls its request-scoped structured decision event; it never substitutes a direct local pipeline result.</p></div>
        <ul className="safety-list"><li>Public quote <strong>{quote?.fallback ? "Fallback" : quote ? "Active" : "Loading"}</strong></li><li>Federated evidence <strong>Loaded</strong></li><li>Agent assessment <strong>{job?.status ?? "Waiting"}</strong></li><li>SuperLink AgentApp <strong>{job?.status ?? "Ready"}</strong></li><li>Broker execution <strong>Disabled</strong></li></ul>
      </section>

      {result && <section className="section"><p className="eyebrow">Typed handoffs</p><h2>Agent contribution trace</h2><ol className="agent-chain">{result.contributions.map((contribution, index) => <li key={contribution.agent}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{contribution.agent}</h3><p>{contribution.summary}</p></div></li>)}</ol></section>}
    </main>
  );
}

export default App;
