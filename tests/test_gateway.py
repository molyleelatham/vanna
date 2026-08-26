import json
import time

import pytest

from vanna_agent.gateway import (
    GatewayError,
    GatewayService,
    SuperLinkRunManager,
    parse_decision_event,
)


ORDER = {
    "pair": "EUR/USD",
    "side": "BUY",
    "size_bucket": "1m-5m",
    "volatility": "high",
    "available_providers": ["LP_A", "LP_B", "LP_C"],
}


class FakeProcess:
    def __init__(self, output: str, returncode: int = 0, delay: float = 0) -> None:
        self.output = output
        self.returncode = returncode
        self.delay = delay

    def communicate(self, timeout: int) -> tuple[str, str]:
        time.sleep(self.delay)
        return self.output, ""

    def kill(self) -> None:
        return


def completed_runner(command, **_kwargs):
    run_config = command[command.index("--run-config") + 1]
    request_id = run_config.split("terminal.request-id='", 1)[1].split("'", 1)[0]
    output = json.dumps(
        {
            "type": "vanna.decision",
            "request_id": request_id,
            "status": "completed",
            "result": {
                "vanna_recommendation": {"provider": "LP_B"},
                "governance": {"action": "HUMAN_REVIEW"},
            },
        }
    )
    return FakeProcess(output, delay=0.03)


def failed_runner(_command, **_kwargs):
    return FakeProcess("Flower run failed", returncode=1)


def wait_for_job(manager: SuperLinkRunManager, job_id: str) -> dict:
    for _ in range(100):
        status = manager.status(job_id)
        if status["status"] in {"completed", "failed"}:
            return status
        time.sleep(0.01)
    raise AssertionError("job did not complete")


def test_gateway_returns_public_quote_fallback_without_key(tmp_path) -> None:
    gateway = GatewayService(approval_path=tmp_path / "queue.jsonl")

    quote = gateway.quote("EUR/USD")

    assert quote["pair"] == "EUR/USD"
    assert quote["source"] in {"alpha-vantage", "local-demo-fallback"}
    assert {"bid", "ask", "timestamp"}.issubset(quote)


def test_gateway_rejects_non_bucketed_or_extra_order_fields(tmp_path) -> None:
    runs = SuperLinkRunManager(runner=completed_runner)
    gateway = GatewayService(approval_path=tmp_path / "queue.jsonl", runs=runs)

    with pytest.raises(GatewayError, match="invalid bucketed"):
        gateway.assess({**ORDER, "client_id": "not-allowed"})


def test_superlink_event_parser_scopes_result_to_request() -> None:
    event = parse_decision_event(
        '{"type":"vanna.decision","request_id":"wrong","status":"completed"}'
        '\n{"event":{"type":"vanna.decision","request_id":"right","status":"completed","result":{}}}',
        "right",
    )

    assert event is not None
    assert event["request_id"] == "right"


def test_gateway_returns_completed_flower_job_and_digest(tmp_path) -> None:
    runs = SuperLinkRunManager(runner=completed_runner)
    gateway = GatewayService(approval_path=tmp_path / "queue.jsonl", runs=runs)

    submitted = gateway.assess(ORDER)
    status = wait_for_job(runs, submitted["job_id"])

    assert status["status"] == "completed"
    assert status["result"]["governance"]["action"] == "HUMAN_REVIEW"
    assert len(status["decision_digest"]) == 64


def test_gateway_does_not_fallback_when_flower_run_fails(tmp_path) -> None:
    runs = SuperLinkRunManager(runner=failed_runner)
    gateway = GatewayService(approval_path=tmp_path / "queue.jsonl", runs=runs)

    submitted = gateway.assess(ORDER)
    status = wait_for_job(runs, submitted["job_id"])

    assert status == {
        "job_id": submitted["job_id"],
        "status": "failed",
        "error": "Flower AgentApp assessment unavailable",
    }


def test_gateway_queues_only_completed_flower_decision(tmp_path) -> None:
    path = tmp_path / "queue.jsonl"
    runs = SuperLinkRunManager(runner=completed_runner)
    gateway = GatewayService(approval_path=path, runs=runs)
    submitted = gateway.assess(ORDER)

    with pytest.raises(GatewayError, match="completed Flower"):
        gateway.queue_for_human_approval({"job_id": submitted["job_id"], "operator_acknowledged": True})

    wait_for_job(runs, submitted["job_id"])
    record = gateway.queue_for_human_approval({"job_id": submitted["job_id"], "operator_acknowledged": True})

    assert record["status"] == "PENDING_HUMAN_APPROVAL"
    assert record["broker_order_sent"] is False
    assert json.loads(path.read_text())["automatic_execution"] is False
