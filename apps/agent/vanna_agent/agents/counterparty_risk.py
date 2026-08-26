"""Explainable provider reliability agent; never a blacklist."""

from __future__ import annotations

from ..connectors import ConnectorClient, ExecutionHistory
from ..domain import ProviderEvidence, Recommendation
from .contracts import CounterpartyRiskAssessment


class CounterpartyRiskAgent:
    name = "CounterpartyRiskAgent"

    def assess(
        self,
        recommendation: Recommendation,
        evidence: list[ProviderEvidence],
        connectors: ConnectorClient | None = None,
    ) -> CounterpartyRiskAssessment:
        item = next(
            (entry for entry in evidence if entry.provider == recommendation.provider),
            None,
        )
        if item is None:
            raise ValueError("recommended provider has no reliability evidence")

        if connectors is not None:
            try:
                live = connectors.execution_history_or_fallback(
                    provider=item.provider,
                    pair="EUR/USD",  # TODO: pass pair from recommendation context
                    size_bucket="1m-5m",  # TODO: pass size_bucket
                )
                # Blend static + live for reliability scoring
                blended_fill = 0.7 * item.fill_probability + 0.3 * live.fill_probability
                blended_latency = 0.7 * item.expected_latency_ms + 0.3 * live.avg_latency_ms
                blended_slippage = 0.7 * item.expected_slippage_bps + 0.3 * live.avg_slippage_bps
                blended_asymmetry = 0.7 * item.rejection_asymmetry  # last_look handles this
                # Use blended values for scoring
                item = ProviderEvidence(
                    provider=item.provider,
                    sample_count=item.sample_count + live.sample_count,
                    fill_probability=blended_fill,
                    rejection_probability=1.0 - blended_fill,
                    expected_slippage_bps=blended_slippage,
                    expected_latency_ms=blended_latency,
                    displayed_price_benefit_bps=item.displayed_price_benefit_bps,
                    rejection_asymmetry=item.rejection_asymmetry,
                    model_version=item.model_version,
                    generated_at=item.generated_at,
                )
            except Exception:
                pass  # Use static item

        latency_score = max(0.0, 1.0 - item.expected_latency_ms / 150.0)
        slippage_score = max(0.0, 1.0 - item.expected_slippage_bps / 3.0)
        asymmetry_score = max(0.0, 1.0 - abs(item.rejection_asymmetry) / 0.3)
        score = round(
            0.5 * item.fill_probability
            + 0.2 * latency_score
            + 0.2 * slippage_score
            + 0.1 * asymmetry_score,
            4,
        )
        confidence = (
            "high"
            if item.sample_count >= 200
            else "medium"
            if item.sample_count >= 50
            else "low"
        )
        posture = (
            "NORMAL"
            if score >= 0.65 and confidence != "low"
            else "REDUCED_SIZE"
            if score >= 0.45
            else "HUMAN_REVIEW"
        )
        return CounterpartyRiskAssessment(
            provider=item.provider,
            reliability_score=score,
            confidence=confidence,
            route_posture=posture,
            factors=[
                f"fill probability {item.fill_probability:.1%}",
                f"expected latency {item.expected_latency_ms:.1f} ms",
                f"expected slippage {item.expected_slippage_bps:.2f} bps",
                f"conditional rejection asymmetry {item.rejection_asymmetry:.3f}",
            ],
        )
