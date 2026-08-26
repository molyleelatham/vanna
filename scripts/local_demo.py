"""Run Vanna's deterministic live path without waiting on a federation or model endpoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/agent"))

from vanna_agent.agent_app import deterministic_answer, run_pipeline  # noqa: E402

ORDER = {
    "pair": "EUR/USD",
    "side": "BUY",
    "size_bucket": "1m-5m",
    "volatility": "high",
    "available_providers": ["LP_A", "LP_B", "LP_C"],
}


def main() -> None:
    result = run_pipeline(json.dumps(ORDER))
    print(deterministic_answer(result))


if __name__ == "__main__":
    main()
