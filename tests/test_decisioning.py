from datetime import UTC, datetime

from vanna_core.decisioning import rank_providers, rejection_asymmetry
from vanna_core.governance import evaluate_governance
from vanna_core.schemas import LastLookSignal, OrderRequest, ProviderEvidence


def evidence(provider: str, fill: float, slippage: float, latency: float, benefit: float):
    return ProviderEvidence(
        provider=provider,
        sample_count=450,
        fill_probability=fill,
        rejection_probability=1 - fill,
        expected_slippage_bps=slippage,
        expected_latency_ms=latency,
        displayed_price_benefit_bps=benefit,
        rejection_asymmetry=0.03,
        model_version="test-v1",
        generated_at=datetime(2026, 8, 26, 11, 25, tzinfo=UTC),
    )


def test_wider_but_reliable_quote_wins() -> None:
    order = OrderRequest(
        pair="EUR/USD",
        side="BUY",
        size_bucket="1m-5m",
        volatility="high",
        available_providers=["LP_A", "LP_B"],
    )
    recommendation = rank_providers(
        order,
        [
            evidence("LP_A", 0.42, 1.1, 78, 0.45),
            evidence("LP_B", 0.78, 0.42, 31, 0.10),
        ],
        now=datetime(2026, 8, 26, 11, 30, tzinfo=UTC),
    )
    assert recommendation.provider == "LP_B"
    assert recommendation.confidence == "high"


def test_last_look_is_review_signal_not_blacklist() -> None:
    asymmetry = rejection_asymmetry(0.31, 0.09)
    assert asymmetry == 0.22
    recommendation = rank_providers(
        OrderRequest(
            pair="EUR/USD",
            side="BUY",
            size_bucket="1m-5m",
            volatility="high",
            available_providers=["LP_B"],
        ),
        [evidence("LP_B", 0.78, 0.42, 31, 0.10)],
        now=datetime(2026, 8, 26, 11, 30, tzinfo=UTC),
    )
    decision = evaluate_governance(
        recommendation,
        LastLookSignal(
            provider="LP_B",
            rejection_asymmetry=asymmetry,
            level="elevated",
            review_required=True,
            explanation="Review signal only.",
        ),
        cohort_size=5,
    )
    assert decision.action == "HUMAN_REVIEW"
    assert decision.automatic_blacklist is False
    assert decision.automatic_execution is False
