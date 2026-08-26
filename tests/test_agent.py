import json

from vanna_agent.agent_app import MAX_AGENT_CALLS, deterministic_answer, run_pipeline
from vanna_agent.agents import HANDOFF_CHAIN


def test_structured_handoff_and_local_fallback() -> None:
    result = run_pipeline(
        json.dumps(
            {
                "pair": "EUR/USD",
                "side": "BUY",
                "size_bucket": "1m-5m",
                "volatility": "high",
                "available_providers": ["LP_A", "LP_B", "LP_C"],
            }
        )
    )
    assert MAX_AGENT_CALLS == 6
    assert result["vanna_recommendation"]["provider"] == "LP_B"
    assert "counterparty_risk" in result
    assert "margin" in result
    assert "manipulation" in result
    assert "governance" in result
    assert result["privacy"] == {
        "raw_records_shared": 0,
        "client_identities_shared": 0,
    }
    answer = deterministic_answer(result, "endpoint unavailable")
    assert "deterministic fallback" in answer
    assert "No automatic execution, blacklist" in answer
    assert "CounterpartyRisk" in answer
    assert "Margin" in answer
    assert "ManipulationWatch" in answer
    assert "Governance" in answer


def test_contributions_render_one_line_per_agent_in_handoff_order() -> None:
    result = run_pipeline(
        json.dumps(
            {
                "pair": "EUR/USD",
                "side": "BUY",
                "size_bucket": "1m-5m",
                "volatility": "high",
                "available_providers": ["LP_A", "LP_B", "LP_C"],
            }
        )
    )
    contributions = result["contributions"]
    assert [c["agent"] for c in contributions] == list(HANDOFF_CHAIN)
    for contribution in contributions:
        assert contribution["summary"]
        assert contribution["assessment"]

    answer = deterministic_answer(result)
    answer_lines = answer.splitlines()
    # Header + one line per agent + privacy footer
    assert answer_lines[0] == f"Handoff: {' -> '.join(HANDOFF_CHAIN)}"
    for contribution in contributions:
        assert f"{contribution['agent']}: {contribution['summary']}" in answer_lines
    assert answer_lines[-1] == "Privacy: 0 raw records and 0 client identities shared."
