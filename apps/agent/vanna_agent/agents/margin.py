"""Advisory margin and settlement-pressure agent."""

from __future__ import annotations

from .contracts import MarginAssessment, MarginContext


class MarginAgent:
    name = "MarginAgent"

    def assess(self, context: MarginContext) -> MarginAssessment:
        leverage_pressure = min(context.leverage_ratio / 20.0, 1.0)
        volatility_pressure = {"calm": 0.1, "normal": 0.4, "high": 1.0}[
            context.volatility
        ]
        score = (
            0.35 * context.margin_utilization
            + 0.20 * leverage_pressure
            + 0.20 * context.correlated_exposure
            + 0.15 * context.settlement_pressure
            + 0.10 * volatility_pressure
        )
        pressure = "high" if score >= 0.72 else "medium" if score >= 0.45 else "low"
        multiplier = 0.5 if pressure == "high" else 0.75 if pressure == "medium" else 1.0
        factors = [
            f"margin utilization {context.margin_utilization:.1%}",
            f"leverage ratio {context.leverage_ratio:.1f}x",
            f"correlated exposure {context.correlated_exposure:.1%}",
            f"settlement pressure {context.settlement_pressure:.1%}",
            f"volatility regime {context.volatility}",
        ]
        return MarginAssessment(
            pressure=pressure,
            recommended_size_multiplier=multiplier,
            human_review_required=pressure == "high",
            factors=factors,
        )
