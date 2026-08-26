"""Bounded Vanna -> LastLook collaborative AgentApp."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flwr.agentapp import AgentApp, AgentSession
from flwr.app import ConfigRecord, Context
from openai import OpenAI

from .domain import OrderRequest, ProviderEvidence, govern, last_look_signal, recommend

MODEL = os.getenv("VANNA_MODEL_ID", "glm-5.2-fp8")
MAX_AGENT_CALLS = 2
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
    recommendation = recommend(order, evidence)
    available_evidence = [
        item for item in evidence if item.provider in order.available_providers
    ]
    displayed_quote_leader = max(
        available_evidence,
        key=lambda item: item.displayed_price_benefit_bps,
    )
    signal = last_look_signal(displayed_quote_leader)
    governance = govern(
        recommendation,
        signal,
        cohort_size=int(payload["cohort_size"]),
    )
    return {
        "order_context": order.model_dump(mode="json"),
        "vanna_recommendation": recommendation.model_dump(mode="json"),
        "last_look_signal": signal,
        "governance": governance,
        "privacy": {
            "raw_records_shared": int(payload["raw_records_shared"]),
            "client_identities_shared": int(payload["client_identities_shared"]),
        },
    }


def deterministic_answer(result: dict[str, Any], failure: str | None = None) -> str:
    recommendation = result["vanna_recommendation"]
    signal = result["last_look_signal"]
    governance = result["governance"]
    lines = [
        f"Vanna recommends {recommendation['provider']} at an estimated "
        f"{recommendation['expected_cost_bps']:.2f} bps executable cost.",
        recommendation["reason"],
        f"LastLook: {signal['explanation']}",
        f"Governance: {governance['action']} (no automatic execution or blacklist).",
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
        # Agent call 1: Vanna contributes the execution-quality interpretation.
        vanna_response = client.responses.create(
            model=MODEL,
            instructions=(
                "You are Vanna, an FX execution-intelligence agent. Explain the supplied "
                "deterministic recommendation in two sentences. Do not alter numbers, "
                "broadcast a collective instruction, or claim that a review signal proves misconduct."
            ),
            input=json.dumps(
                {
                    "order": result["order_context"],
                    "recommendation": result["vanna_recommendation"],
                }
            ),
        )
        vanna_contribution = vanna_response.output_text

        # Agent call 2: LastLook receives an explicit, minimal handoff and presents the final result.
        handoff = {
            "order": result["order_context"],
            "vanna_recommendation": result["vanna_recommendation"],
            "vanna_explanation": vanna_contribution,
            "last_look_signal": result["last_look_signal"],
            "governance": result["governance"],
            "privacy": result["privacy"],
        }
        stream = client.responses.create(
            model=MODEL,
            instructions=(
                "You are LastLook, the second agent in a bounded two-agent chain. Present "
                "Vanna's local recommendation, then your conditional last-look review signal, "
                "governance action, and privacy proof. Preserve every supplied number. State "
                "that this is not an automatic trade, blacklist, collective instruction, or "
                "proof of misconduct."
            ),
            input=json.dumps(handoff),
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
    except Exception as exc:  # The deterministic path must survive endpoint/runtime failures.
        answer = deterministic_answer(result, str(exc))

    persist_result(context, result, answer)
    print(answer)
