"""Advisory margin and settlement-pressure agent."""

from __future__ import annotations

from ..connectors import ConnectorClient, RiskMetrics
from .contracts import MarginAssessment, MarginContext


class MarginAgent:
    name = "MarginAgent"

    def assess(
        self,
        context: MarginContext,
        connectors: ConnectorClient | None = None,
    ) -> MarginAssessment:
        # If connectors available, use live risk metrics; else use context
        if connectors is not None:
            try:
                live = connectors.risk_metrics_or_fallback(pair=context.pair)
                margin_utilization = live.margin_utilization
                leverage_ratio = live.leverage_ratio
                correlated_exposure = live.correlated_exposure
                settlement_pressure = live.settlement_pressure
            except Exception:
                margin_utilization = context.margin_utilization
                leverage_ratio = context.leverage_ratio
                correlated_exposure = context.correlated_exposure
                settlement_pressure = context.settlement_pressure
        else:
            margin_utilization = context.margin_utilization
            leverage_ratio = context.leverage_ratio
            correlated_exposure = context.correlated_exposure
            settlement_pressure = context.settlement_pressure

        leverage_pressure = min(leverage_ratio / 20.0, 1.0)
        volatility_pressure = {"calm": 0.1, "normal": 0.4, "high": 1.0}[
            context.volatility
        ]
        score = (
            0.35 * margin_utilization
            + 0.20 * leverage_pressure
            + 0.20 * correlated_exposure
            + 0.15 * settlement_pressure
            + 0.10 * volatility_pressure
        )
        pressure = "high" if score >= 0.72 else "medium" if score >= 0.45 else "low"
        multiplier = 0.5 if pressure == "high" else 0.75 if pressure == "medium" else 1.0
        factors = [
            f"margin utilization {margin_utilization:.1%}",
            f"leverage ratio {leverage_ratio:.1f}x",
            f"correlated exposure {correlated_exposure:.1%}",
            f"settlement pressure {settlement_pressure:.1%}",
            f"volatility regime {context.volatility}",
        ]
        return MarginAssessment(
            pressure=pressure,
            recommended_size_multiplier=multiplier,
            human_review_required=pressure == "high",
            factors=factors,
        )

    def explain(self, assessment: MarginAssessment) -> str:
        """Deterministic narration of margin pressure; advisory only."""
        return (
            f"Margin pressure {assessment.pressure}; recommended size multiplier "
            f"{assessment.recommended_size_multiplier:.2f}; human review: "
            f"{'yes' if assessment.human_review_required else 'no'}. "
            f"Factors: {', '.join(assessment.factors)}. No automatic liquidation."
        )
