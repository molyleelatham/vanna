import json

from vanna_agent.agent_app import MAX_AGENT_CALLS, deterministic_answer, run_pipeline


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
    assert "no auto-execution or blacklist" in answer
    assert "CounterpartyRisk" in answer
    assert "Margin" in answer
    assert "ManipulationWatch" in answer
    assert "Governance" in answer
