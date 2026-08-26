"""Local-only browser gateway for real local-SuperLink AgentApp runs.

This gateway never sends a broker/OMS order. Its only consequential action is
to create a local, non-executable human-approval record after a Flower AgentApp
run has completed with a governed decision.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

from pydantic import ValidationError

from .connectors import AlphaVantageClient
from .domain import OrderRequest

DEFAULT_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}
DEFAULT_APPROVAL_PATH = Path(__file__).parents[1] / "artifacts" / "approval_queue.jsonl"
AGENT_DIRECTORY = Path(__file__).parents[1]
FALLBACK_QUOTES = {
    "EUR/USD": {"bid": 1.0800, "ask": 1.0802},
    "GBP/USD": {"bid": 1.2700, "ask": 1.2703},
    "GBP/JPY": {"bid": 190.50, "ask": 190.55},
    "USD/JPY": {"bid": 150.00, "ask": 150.03},
}


class GatewayError(ValueError):
    """A safe error that can be returned to the local UI."""


@dataclass
class DecisionJob:
    request_id: str
    order: dict[str, Any]
    status: str = "queued"
    result: dict[str, Any] | None = None
    decision_digest: str | None = None
    error: str | None = None


def _strip_terminal_codes(value: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)


def _find_decision_event(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if value.get("type") == "vanna.decision":
            return value
        for child in value.values():
            found = _find_decision_event(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_decision_event(child)
            if found:
                return found
    return None


def parse_decision_event(stream_output: str, request_id: str) -> dict[str, Any] | None:
    """Find the request-scoped custom AgentApp event in Flower CLI output."""
    decoder = json.JSONDecoder()
    cleaned = _strip_terminal_codes(stream_output)
    for line in cleaned.splitlines():
        if line.startswith("VANNA_TERMINAL_EVENT="):
            try:
                event = json.loads(line.removeprefix("VANNA_TERMINAL_EVENT="))
            except json.JSONDecodeError:
                continue
            if event.get("request_id") == request_id and event.get("type") == "vanna.decision":
                return event
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        event = _find_decision_event(parsed)
        if event and event.get("request_id") == request_id:
            return event
    return None


class SuperLinkRunManager:
    def __init__(
        self,
        *,
        agent_directory: Path = AGENT_DIRECTORY,
        runner: Callable[..., Any] = subprocess.Popen,
        timeout_seconds: int = 120,
    ) -> None:
        self.agent_directory = agent_directory
        self.runner = runner
        self.timeout_seconds = timeout_seconds
        self.jobs: dict[str, DecisionJob] = {}
        self._lock = threading.Lock()

    def submit(self, payload: object) -> DecisionJob:
        try:
            order = OrderRequest.model_validate(payload)
        except ValidationError as exc:
            raise GatewayError("invalid bucketed order input") from exc

        request_id = str(uuid4())
        job = DecisionJob(request_id=request_id, order=order.model_dump(mode="json"))
        with self._lock:
            self.jobs[request_id] = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def status(self, request_id: str) -> dict[str, Any]:
        try:
            canonical_id = str(UUID(request_id))
        except ValueError as exc:
            raise GatewayError("invalid decision job ID") from exc
        with self._lock:
            job = self.jobs.get(canonical_id)
            if job is None:
                raise GatewayError("decision job not found")
            response: dict[str, Any] = {
                "job_id": job.request_id,
                "status": job.status,
            }
            if job.status == "completed":
                response["result"] = job.result
                response["decision_digest"] = job.decision_digest
            if job.status == "failed":
                response["error"] = job.error
            return response

    def completed_job(self, request_id: str) -> DecisionJob:
        self.status(request_id)  # Validate the ID and ensure it exists.
        with self._lock:
            job = self.jobs[request_id]
            if job.status != "completed" or not job.decision_digest:
                raise GatewayError("a completed Flower decision is required")
            return job

    def _run(self, job: DecisionJob) -> None:
        with self._lock:
            job.status = "running"
        command = [
            "uv",
            "run",
            "flwr",
            "run",
            ".",
            "local-superlink",
            "--stream",
            "--run-config",
            (
                f"agent.input='{json.dumps(job.order, separators=(',', ':'))}' "
                f"terminal.request-id='{job.request_id}' "
                f"model-id='{os.getenv('VANNA_TERMINAL_MODEL_ID', '/models/Qwen3.5-397B-A17B-FP8')}'"
            ),
        ]
        try:
            process = self.runner(
                command,
                cwd=self.agent_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            output, _ = process.communicate(timeout=self.timeout_seconds)
            event = parse_decision_event(output or "", job.request_id)
            if process.returncode != 0:
                raise GatewayError("Flower AgentApp run failed")
            if event is None:
                raise GatewayError("Flower run returned no terminal decision event")
            if event.get("status") != "completed" or not isinstance(event.get("result"), dict):
                raise GatewayError("Flower AgentApp did not complete the assessment")

            result = event["result"]
            digest = hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            with self._lock:
                job.status = "completed"
                job.result = result
                job.decision_digest = digest
        except subprocess.TimeoutExpired:
            try:
                process.kill()  # type: ignore[has-type]
            except Exception:
                pass
            with self._lock:
                job.status = "failed"
                job.error = "Flower AgentApp run timed out"
        except Exception:
            with self._lock:
                job.status = "failed"
                job.error = "Flower AgentApp assessment unavailable"


class GatewayService:
    def __init__(
        self,
        *,
        approval_path: Path = DEFAULT_APPROVAL_PATH,
        quote_client: AlphaVantageClient | None = None,
        runs: SuperLinkRunManager | None = None,
    ) -> None:
        self.approval_path = approval_path
        self.quote_client = quote_client
        self.runs = runs or SuperLinkRunManager()

    def quote(self, pair: str) -> dict[str, Any]:
        if pair not in FALLBACK_QUOTES:
            raise GatewayError("unsupported pair")
        try:
            client = self.quote_client or AlphaVantageClient()
            response = client.get_fx_rate(pair)
            return {
                "pair": pair,
                "bid": response["bid"],
                "ask": response["ask"],
                "timestamp": response.get("timestamp") or datetime.now(UTC).isoformat(),
                "source": "alpha-vantage",
                "fallback": False,
            }
        except Exception:
            return {
                "pair": pair,
                **FALLBACK_QUOTES[pair],
                "timestamp": datetime.now(UTC).isoformat(),
                "source": "local-demo-fallback",
                "fallback": True,
            }

    def assess(self, payload: object) -> dict[str, Any]:
        job = self.runs.submit(payload)
        return {"job_id": job.request_id, "status": job.status}

    def decision_status(self, request_id: str) -> dict[str, Any]:
        return self.runs.status(request_id)

    def connectivity(self) -> dict[str, Any]:
        """Report the local handoff links without exposing runtime credentials."""
        try:
            with socket.create_connection(("127.0.0.1", 9093), timeout=0.5):
                superlink_status = "reachable"
        except OSError:
            superlink_status = "unreachable"
        return {
            "gateway": "reachable",
            "superlink": superlink_status,
            "superlink_endpoint": "127.0.0.1:9093",
            "agentapp_mode": "on-demand Flower run",
            "data_boundary": "approved aggregate evidence only",
        }

    def queue_for_human_approval(self, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict) or payload.get("operator_acknowledged") is not True:
            raise GatewayError("operator acknowledgement is required")
        request_id = payload.get("job_id")
        if not isinstance(request_id, str):
            raise GatewayError("a Flower decision job ID is required")
        job = self.runs.completed_job(request_id)

        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "status": "PENDING_HUMAN_APPROVAL",
            "order": job.order,
            "decision_digest": job.decision_digest,
            "governance_action": job.result["governance"]["action"] if job.result else None,
            "operator_acknowledged": True,
            "flower_job_id": job.request_id,
            "broker_order_sent": False,
            "automatic_execution": False,
        }
        self.approval_path.parent.mkdir(parents=True, exist_ok=True)
        with self.approval_path.open("a", encoding="utf-8") as queue:
            queue.write(json.dumps(record, sort_keys=True) + "\n")
        return record


def _allowed_origins() -> set[str]:
    configured = os.getenv("VANNA_DASHBOARD_ORIGINS")
    return (
        {origin.strip() for origin in configured.split(",") if origin.strip()}
        if configured
        else DEFAULT_ORIGINS
    )


def make_handler(service: GatewayService) -> type[BaseHTTPRequestHandler]:
    class GatewayHandler(BaseHTTPRequestHandler):
        def _origin(self) -> str | None:
            origin = self.headers.get("Origin")
            return origin if origin in _allowed_origins() else None

        def _send(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            origin = self._origin()
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> object:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 32_768:
                raise GatewayError("request body must be a small JSON object")
            return json.loads(self.rfile.read(length))

        def do_OPTIONS(self) -> None:  # noqa: N802
            origin = self._origin()
            if not origin:
                self._send(HTTPStatus.FORBIDDEN, {"error": "origin not allowed"})
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Vary", "Origin")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/quote":
                    pair = parse_qs(parsed.query).get("pair", ["EUR/USD"])[0]
                    self._send(HTTPStatus.OK, service.quote(pair))
                elif parsed.path == "/api/connectivity":
                    self._send(HTTPStatus.OK, service.connectivity())
                elif parsed.path.startswith("/api/decisions/"):
                    request_id = parsed.path.removeprefix("/api/decisions/")
                    self._send(HTTPStatus.OK, service.decision_status(request_id))
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except GatewayError as exc:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            try:
                payload = self._read_json()
                if path == "/api/decision":
                    self._send(HTTPStatus.ACCEPTED, service.assess(payload))
                elif path == "/api/approval-queue":
                    self._send(HTTPStatus.CREATED, service.queue_for_human_approval(payload))
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except (GatewayError, json.JSONDecodeError) as exc:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "decision service unavailable"})

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return GatewayHandler


def serve(host: str = "127.0.0.1", port: int = 8010) -> None:
    print(f"Vanna local gateway listening at http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), make_handler(GatewayService())).serve_forever()


if __name__ == "__main__":
    serve()
