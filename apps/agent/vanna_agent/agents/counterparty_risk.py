"""Explainable provider reliability agent; never a blacklist."""

from __future__ import annotations

from ..domain import ProviderEvidence, Recommendation
from .contracts import CounterpartyRiskAssessment


class CounterpartyRiskAgent:
    name = "CounterpartyRiskAgent"

    def assess(
        self,
        recommendation: Recommendation,
        evidence: list[ProviderEvidence],
    ) -> CounterpartyRiskAssessment:
        item = next(
            (entry for entry in evidence if entry.provider == recommendation.provider),
            None,
        )
        if item is None:
            raise ValueError("recommended provider has no reliability evidence")

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
