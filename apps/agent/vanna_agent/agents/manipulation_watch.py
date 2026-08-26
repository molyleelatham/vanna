"""Market-pattern surveillance agent producing review signals only."""

from __future__ import annotations

from ..connectors import ConnectorClient, SurveillanceSignal
from .contracts import ManipulationAssessment, MarketPatternContext


class ManipulationWatch:
    name = "ManipulationWatch"

    def assess(
        self,
        context: MarketPatternContext,
        connectors: ConnectorClient | None = None,
    ) -> ManipulationAssessment:
        # Use live surveillance signal only when genuinely live; else context.
        # Fallback constants are never blended in.
        live = (
            connectors.surveillance_signal_if_live(provider=context.provider, window="24h")
            if connectors is not None
            else None
        )
        if live is not None:
            quote_to_trade_ratio = live.quote_to_trade_ratio
            cancellation_rate = live.cancellation_rate
            synchronized_quote_score = live.synchronized_quote_score
            cross_pair_anomaly_score = live.cross_pair_anomaly_score
            pre_movement_activity_score = live.pre_movement_activity_score
            sample_count = live.sample_count
        else:
            quote_to_trade_ratio = context.quote_to_trade_ratio
            cancellation_rate = context.cancellation_rate
            synchronized_quote_score = context.synchronized_quote_score
            cross_pair_anomaly_score = context.cross_pair_anomaly_score
            pre_movement_activity_score = context.pre_movement_activity_score
            sample_count = context.sample_count

        quote_activity = min(quote_to_trade_ratio / 50.0, 1.0)
        score = round(
            0.20 * quote_activity
            + 0.25 * cancellation_rate
            + 0.20 * synchronized_quote_score
            + 0.20 * cross_pair_anomaly_score
            + 0.15 * pre_movement_activity_score,
            4,
        )
        if sample_count < 50:
            signal = "watch" if score >= 0.45 else "normal"
        else:
            signal = "review" if score >= 0.72 else "watch" if score >= 0.45 else "normal"
        factors = [
            f"quote-to-trade ratio {quote_to_trade_ratio:.1f}",
            f"cancellation rate {cancellation_rate:.1%}",
            f"synchronized quote score {synchronized_quote_score:.2f}",
            f"cross-pair anomaly score {cross_pair_anomaly_score:.2f}",
            f"pre-movement activity score {pre_movement_activity_score:.2f}",
        ]
        if sample_count < 50:
            factors.append("insufficient sample for a high-confidence review signal")
        return ManipulationAssessment(
            provider=context.provider,
            signal=signal,
            anomaly_score=score,
            human_review_required=signal == "review",
            factors=factors,
        )

    def explain(self, assessment: ManipulationAssessment) -> str:
        """Deterministic narration of the surveillance signal; never a misconduct finding."""
        return (
            f"{assessment.provider} surveillance signal {assessment.signal} "
            f"(anomaly score {assessment.anomaly_score:.2f}); human review: "
            f"{'yes' if assessment.human_review_required else 'no'}. "
            f"Factors: {', '.join(assessment.factors)}. "
            "Review signal only — not a misconduct finding."
        )
