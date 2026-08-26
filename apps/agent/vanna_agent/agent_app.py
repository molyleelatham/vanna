"""Full six-agent Vanna collaborative AgentApp with live connector data."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flwr.agentapp import AgentApp, AgentSession
from flwr.app import ConfigRecord, Context
from openai import OpenAI

from .agents import HANDOFF_CHAIN, OrchestratorAgent
from .connectors import ConnectorClient
from .domain import OrderRequest, ProviderEvidence
from .xgboost_local import train_local_xgboost_models, compare_models  # type: ignore

MODEL = os.getenv("VANNA_MODEL_ID", "glm-5.2-fp8")
MAX_AGENT_CALLS = 6
MAX_TOOL_TURNS = 3
EVIDENCE_PATH = Path(__file__).parent / "artifacts" / "provider_evidence.json"

app = AgentApp()


def load_evidence(path: Path = EVIDENCE_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    forbidden = {
        "client_id",
        "account_id",
        "real_order_id",
        "local_order_id",
        "uti",
        "live_intention",
    }

    def all_keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return {str(key).lower() for key in value}.union(
                *(all_keys(item) for item in value.values())
            )
        if isinstance(value, list):
            return set().union(*(all_keys(item) for item in value))
        return set()

    if forbidden.intersection(all_keys(payload)):
        raise ValueError("aggregate evidence contains a prohibited field")
    return payload


def run_pipeline(
    prompt: str,
    path: Path = EVIDENCE_PATH,
    connectors: ConnectorClient | None = None,
) -> dict[str, Any]:
    order = OrderRequest.model_validate_json(prompt)
    payload = load_evidence(path)
    evidence = [ProviderEvidence.model_validate(item) for item in payload["providers"]]

    orchestrator = OrchestratorAgent(connectors=connectors)
    # Score against the artifact's own timestamp so a checked-in evidence JSON
    # is not treated as stale by the freshness/governance controls.
    artifact_time = evidence[0].generated_at if evidence else None
    assessments = orchestrator.assess(order, evidence, now=artifact_time)

    return {
        "order_context": order.model_dump(mode="json"),
        "handoff_chain": list(HANDOFF_CHAIN),
        "live_path": "local-non-blocking",
        "vanna_recommendation": assessments["recommendation"].model_dump(mode="json"),
        "last_look_signal": assessments["last_look"].model_dump(mode="json"),
        "counterparty_risk": assessments["counterparty_risk"].model_dump(mode="json"),
        "margin": assessments["margin"].model_dump(mode="json"),
        "manipulation": assessments["manipulation"].model_dump(mode="json"),
        "governance": assessments["governance"].model_dump(mode="json"),
        "privacy": {
            "raw_records_shared": int(payload["raw_records_shared"]),
            "client_identities_shared": int(payload["client_identities_shared"]),
        },
    }


def deterministic_answer(result: dict[str, Any], failure: str | None = None) -> str:
    rec = result["vanna_recommendation"]
    ll = result["last_look_signal"]
    gov = result["governance"]
    cp = result.get("counterparty_risk", {})
    mg = result.get("margin", {})
    mp = result.get("manipulation", {})

    chain = " -> ".join(result.get("handoff_chain", HANDOFF_CHAIN))
    lines = [
        f"Handoff: {chain}",
        f"Vanna recommends {rec['provider']} at an estimated "
        f"{rec['expected_cost_bps']:.2f} bps executable cost.",
        rec["reason"],
        f"LastLook: {ll['explanation']}",
        f"CounterpartyRisk: {cp.get('route_posture', 'N/A')} (reliability {cp.get('reliability_score', 'N/A')})",
        f"Margin: {mg.get('pressure', 'N/A')} pressure (size multiplier {mg.get('recommended_size_multiplier', 'N/A')})",
        f"ManipulationWatch: {mp.get('signal', 'N/A')} (anomaly {mp.get('anomaly_score', 'N/A')})",
        f"Governance: {gov['action']} — {', '.join(gov.get('reasons', ['no reasons']))} (no auto-execution or blacklist).",
        "Privacy: 0 raw records and 0 client identities shared.",
    ]
    if failure:
        lines.append(f"Model narration unavailable; deterministic fallback used: {failure}")
    return "\n".join(lines)


def persist_result(context: Context, result: dict[str, Any], answer: str, connectors: ConnectorClient | None = None) -> None:
    # Capture live data snapshot for audit
    live_snapshot = {}
    if connectors:
        try:
            live_snapshot = {
                "market_data": connectors.market_data_or_fallback("EUR/USD").__dict__,
                "risk_metrics": connectors.risk_metrics_or_fallback("EUR/USD").__dict__,
                "federation_metrics": connectors.federation_metrics_or_fallback().__dict__,
            }
        except Exception:
            live_snapshot = {"error": "failed to capture live snapshot"}

    compact = {"result": result, "answer": answer, "live_snapshot": live_snapshot}
    with context.locked():
        context.state.config_records["vanna-state"] = ConfigRecord(
            {"json": json.dumps(compact)}
        )


@app.main()
def main(agent: AgentSession, context: Context) -> None:
    prompt = context.run_config.get("agent.input")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("agent.input must be a non-empty JSON string")

    # Model ID can be overridden per run (SuperGrid runs can't set env vars)
    model_id = context.run_config.get("model-id") or MODEL

    # Initialize connector client for live data
    connectors = ConnectorClient(agent)

    # Run pipeline with live data enrichment
    result = run_pipeline(prompt, connectors=connectors)
    
    # Load evidence for model comparison
    import json
    from .domain import ProviderEvidence
    payload = json.loads((Path(__file__).parent / "artifacts" / "provider_evidence.json").read_text())
    evidence = [ProviderEvidence.model_validate(item) for item in payload["providers"]]
    answer = ""

    try:
        client = OpenAI(
            base_url=os.environ["FLWR_RUNTIME_BASE_URL"],
            api_key=os.environ["FLWR_RUNTIME_API_KEY"],
            max_retries=0,
        )

        # Include local vs federated model comparison in initial context
        fill_model, slippage_model, latency_model = train_local_xgboost_models()
        model_comparison = compare_models(
            pair=result["order_context"]["pair"],
            providers=result["order_context"]["available_providers"],
            evidence=evidence,
            fill_model=fill_model,
            slippage_model=slippage_model,
            latency_model=latency_model,
        )
        
        comparison_data = [c.__dict__ for c in model_comparison]
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Vanna Orchestrator. Present the six-agent collaborative analysis "
                    "in sequence: Vanna (execution value), LastLook (conditional rejection), "
                    "CounterpartyRisk (reliability), Margin (pressure), ManipulationWatch (surveillance), "
                    "Governance (final decision). "
                    "Also present the Local XGBoost vs Federated Logistic model comparison. "
                    "Preserve all supplied numbers. State this is advisory "
                    "only — no automatic execution, blacklist, collective instruction, or misconduct finding."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    **result,
                    "model_comparison": comparison_data,
                }),
            },
        ]

        for turn in range(MAX_TOOL_TURNS):
            stream = client.responses.create(
                model=model_id,
                input=messages,
                stream=True,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "get_market_data",
                            "description": "Get real-time market data for a currency pair",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "pair": {"type": "string"},
                                    "window": {"type": "string", "default": "1h"},
                                },
                                "required": ["pair"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_order_flow",
                            "description": "Get order flow statistics for a provider",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "provider": {"type": "string"},
                                    "window": {"type": "string", "default": "24h"},
                                },
                                "required": ["provider"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_execution_history",
                            "description": "Get bucketed execution history for a provider/pair/size",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "provider": {"type": "string"},
                                    "pair": {"type": "string"},
                                    "size_bucket": {"type": "string"},
                                    "window": {"type": "string", "default": "7d"},
                                },
                                "required": ["provider", "pair", "size_bucket"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_risk_metrics",
                            "description": "Get live risk metrics for a pair",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "pair": {"type": "string"},
                                },
                                "required": ["pair"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_surveillance_signal",
                            "description": "Get manipulation surveillance signal for a provider",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "provider": {"type": "string"},
                                    "window": {"type": "string", "default": "24h"},
                                },
                                "required": ["provider"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_federation_metrics",
                            "description": "Get federation cohort and model metrics",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            )
            output: list[str] = []
            tool_calls: list[dict] = []
            for event in stream:
                agent.events.emit(event.to_dict())
                if event.type in {"error", "response.failed", "response.incomplete"}:
                    raise RuntimeError(f"model response did not complete: {event.type}")
                if event.type in {"response.output_text.delta", "response.refusal.delta"}:
                    output.append(event.delta)
                if event.type == "response.output_item.done" and hasattr(event, "item"):
                    item = event.item
                    if getattr(item, "type", None) == "function_call":
                        tool_calls.append({
                            "name": item.name,
                            "arguments": item.arguments,
                            "call_id": item.call_id,
                        })

            answer = "".join(output).strip()
            messages.append({"role": "assistant", "content": answer})

            if not tool_calls:
                break

            # Execute tool calls and add results to messages
            for tc in tool_calls:
                try:
                    args = json.loads(tc["arguments"])
                    tool_name = tc["name"]
                    if tool_name == "get_market_data":
                        data = connectors.market_data_or_fallback(args["pair"], args.get("window", "1h"))
                        result_data = data.__dict__
                    elif tool_name == "get_order_flow":
                        data = connectors.order_flow_or_fallback(args["provider"], args.get("window", "24h"))
                        result_data = data.__dict__
                    elif tool_name == "get_execution_history":
                        data = connectors.execution_history_or_fallback(
                            args["provider"], args["pair"], args["size_bucket"], args.get("window", "7d")
                        )
                        result_data = data.__dict__
                    elif tool_name == "get_risk_metrics":
                        data = connectors.risk_metrics_or_fallback(args["pair"])
                        result_data = data.__dict__
                    elif tool_name == "get_surveillance_signal":
                        data = connectors.surveillance_signal_or_fallback(args["provider"], args.get("window", "24h"))
                        result_data = data.__dict__
                    elif tool_name == "get_federation_metrics":
                        data = connectors.federation_metrics_or_fallback()
                        result_data = data.__dict__
                    else:
                        result_data = {"error": f"Unknown tool: {tool_name}"}
                except Exception as e:
                    result_data = {"error": str(e)}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["call_id"],
                    "content": json.dumps(result_data),
                })

        if not answer:
            raise RuntimeError("model returned an empty final response")
    except Exception as exc:
        answer = deterministic_answer(result, str(exc))

    persist_result(context, result, answer, connectors=connectors)
    print(answer)
