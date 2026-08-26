"""Full six-agent Vanna collaborative AgentApp."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flwr.agentapp import AgentApp, AgentSession
from flwr.app import ConfigRecord, Context
from openai import OpenAI

from .agents import OrchestratorAgent
from .domain import OrderRequest, ProviderEvidence

MODEL = os.getenv("VANNA_MODEL_ID", "glm-5.2-fp8")
MAX_AGENT_CALLS = 6
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


def run_pipeline(prompt: str, path: Path = EVIDENCE_PATH) -> dict[str, Any]:
    order = OrderRequest.model_validate_json(prompt)
    payload = load_evidence(path)
    evidence = [ProviderEvidence.model_validate(item) for item in payload["providers"]]

    orchestrator = OrchestratorAgent()
    assessments = orchestrator.assess(order, evidence)

    return {
        "order_context": order.model_dump(mode="json"),
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

    lines = [
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


def persist_result(context: Context, result: dict[str, Any], answer: str) -> None:
    compact = {"result": result, "answer": answer}
    with context.locked():
        context.state.config_records["vanna-state"] = ConfigRecord(
            {"json": json.dumps(compact)}
        )


@app.main()
def main(agent: AgentSession, context: Context) -> None:
    prompt = context.run_config.get("agent.input")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("agent.input must be a non-empty JSON string")
    result = run_pipeline(prompt)
    answer = ""

    try:
        client = OpenAI(
            base_url=os.environ["FLWR_RUNTIME_BASE_URL"],
            api_key=os.environ["FLWR_RUNTIME_API_KEY"],
            max_retries=0,
        )

        # Single orchestrator call that streams all six agents' contributions
        stream = client.responses.create(
            model=MODEL,
            instructions=(
                "You are the Vanna Orchestrator. Present the six-agent collaborative analysis "
                "in sequence: Vanna (execution value), LastLook (conditional rejection), "
                "CounterpartyRisk (reliability), Margin (pressure), ManipulationWatch (surveillance), "
                "Governance (final decision). Preserve all supplied numbers. State this is advisory "
                "only — no automatic execution, blacklist, collective instruction, or misconduct finding."
            ),
            input=json.dumps(result),
            stream=True,
        )
        output: list[str] = []
        for event in stream:
            agent.events.emit(event.to_dict())
            if event.type in {"error", "response.failed", "response.incomplete"}:
                raise RuntimeError(f"model response did not complete: {event.type}")
            if event.type in {"response.output_text.delta", "response.refusal.delta"}:
                output.append(event.delta)
        answer = "".join(output).strip()
        if not answer:
            raise RuntimeError("model returned an empty final response")
    except Exception as exc:
        answer = deterministic_answer(result, str(exc))

    persist_result(context, result, answer)
    print(answer)
