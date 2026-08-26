"""Market-pattern surveillance agent producing review signals only."""

from __future__ import annotations

from .contracts import ManipulationAssessment, MarketPatternContext


class ManipulationWatch:
    name = "ManipulationWatch"

    def assess(self, context: MarketPatternContext) -> ManipulationAssessment:
        quote_activity = min(context.quote_to_trade_ratio / 50.0, 1.0)
        score = round(
            0.20 * quote_activity
            + 0.25 * context.cancellation_rate
            + 0.20 * context.synchronized_quote_score
            + 0.20 * context.cross_pair_anomaly_score
            + 0.15 * context.pre_movement_activity_score,
            4,
        )
        if context.sample_count < 50:
            signal = "watch" if score >= 0.45 else "normal"
        else:
            signal = "review" if score >= 0.72 else "watch" if score >= 0.45 else "normal"
        factors = [
            f"quote-to-trade ratio {context.quote_to_trade_ratio:.1f}",
            f"cancellation rate {context.cancellation_rate:.1%}",
            f"synchronized quote score {context.synchronized_quote_score:.2f}",
            f"cross-pair anomaly score {context.cross_pair_anomaly_score:.2f}",
            f"pre-movement activity score {context.pre_movement_activity_score:.2f}",
        ]
        if context.sample_count < 50:
            factors.append("insufficient sample for a high-confidence review signal")
        return ManipulationAssessment(
            provider=context.provider,
            signal=signal,
            anomaly_score=score,
            human_review_required=signal == "review",
            factors=factors,
        )
