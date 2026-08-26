"""Deterministic execution-quality calculations used before any LLM call."""

from __future__ import annotations

from datetime import UTC, datetime

from .schemas import OrderRequest, ProviderEvidence, Recommendation


def rejection_asymmetry(client_favourable_reject_rate: float, adverse_reject_rate: float) -> float:
    for value in (client_favourable_reject_rate, adverse_reject_rate):
        if not 0 <= value <= 1:
            raise ValueError("reject rates must be between zero and one")
    return client_favourable_reject_rate - adverse_reject_rate


def expected_execution_cost(evidence: ProviderEvidence) -> float:
    """Lower is better; a tight displayed quote can still be expensive to execute."""
    rejection_cost = evidence.rejection_probability * 2.5
    latency_cost = evidence.expected_latency_ms / 100.0
    fill_penalty = (1.0 - evidence.fill_probability) * 2.0
    return round(
        evidence.expected_slippage_bps
        + rejection_cost
        + latency_cost
        + fill_penalty
        - evidence.displayed_price_benefit_bps,
        4,
    )


def rank_providers(
    order: OrderRequest,
    evidence: list[ProviderEvidence],
    *,
    now: datetime | None = None,
) -> Recommendation:
    available = [item for item in evidence if item.provider in order.available_providers]
    if not available:
        raise ValueError("no evidence for an available provider")
    selected = min(available, key=expected_execution_cost)
    current_time = now or datetime.now(UTC)
    generated_at = selected.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    freshness = max(0, int((current_time - generated_at).total_seconds()))
    if selected.sample_count >= 200 and freshness <= 900:
        confidence = "high"
    elif selected.sample_count >= 50 and freshness <= 3600:
        confidence = "medium"
    else:
        confidence = "low"
    cost = expected_execution_cost(selected)
    return Recommendation(
        provider=selected.provider,
        expected_cost_bps=cost,
        expected_fill_probability=selected.fill_probability,
        confidence=confidence,
        reason=(
            f"{selected.provider} has the lowest estimated executable cost ({cost:.2f} bps) "
            "after fill, rejection, slippage, and latency effects."
        ),
        model_version=selected.model_version,
        data_freshness_seconds=freshness,
    )
