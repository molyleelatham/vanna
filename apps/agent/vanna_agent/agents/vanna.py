"""Primary expected-execution-value agent."""

from __future__ import annotations

from datetime import datetime

from ..connectors import ConnectorClient, ExecutionHistory
from ..domain import OrderRequest, ProviderEvidence, Recommendation, recommend


class VannaAgent:
    name = "Vanna"

    def assess(
        self,
        order: OrderRequest,
        evidence: list[ProviderEvidence],
        connectors: ConnectorClient | None = None,
        *,
        now: datetime | None = None,
    ) -> Recommendation:
        # Start with static federation evidence
        base_recommendation = recommend(order, evidence, now=now)

        if connectors is None:
            return base_recommendation

        # Enrich with live execution history per available provider
        live_evidence = []
        for provider in order.available_providers:
            try:
                live = connectors.execution_history_or_fallback(
                    provider=provider,
                    pair=order.pair,
                    size_bucket=order.size_bucket,
                )
                # Blend static evidence (federation) with live connector data
                static = next((e for e in evidence if e.provider == provider), None)
                if static:
                    blended = self._blend_evidence(static, live)
                    live_evidence.append(blended)
                else:
                    live_evidence.append(live)
            except Exception:
                # Fallback to static only
                static = next((e for e in evidence if e.provider == provider), None)
                if static:
                    live_evidence.append(static)

        if live_evidence:
            return recommend(order, live_evidence, now=now)
        return base_recommendation

    def explain(self, recommendation: Recommendation) -> str:
        """Deterministic narration of the ranking; numbers come from the assessment."""
        return (
            f"Ranked {recommendation.provider} first at an estimated "
            f"{recommendation.expected_cost_bps:.2f} bps executable cost "
            f"(fill probability {recommendation.expected_fill_probability:.1%}, "
            f"confidence {recommendation.confidence}, model {recommendation.model_version}). "
            f"{recommendation.reason}"
        )

    def _blend_evidence(self, static: ProviderEvidence, live: ExecutionHistory) -> ProviderEvidence:
        """Blend federation evidence (static) with live connector data.
        Weight: 70% federation (larger sample), 30% live (more current).
        """
        weight_fed = 0.7
        weight_live = 0.3
        return ProviderEvidence(
            provider=static.provider,
            sample_count=static.sample_count + live.sample_count,
            fill_probability=weight_fed * static.fill_probability + weight_live * live.fill_probability,
            rejection_probability=weight_fed * static.rejection_probability + weight_live * live.rejection_probability,
            expected_slippage_bps=weight_fed * static.expected_slippage_bps + weight_live * live.avg_slippage_bps,
            expected_latency_ms=weight_fed * static.expected_latency_ms + weight_live * live.avg_latency_ms,
            displayed_price_benefit_bps=static.displayed_price_benefit_bps,
            rejection_asymmetry=static.rejection_asymmetry,
            model_version=static.model_version,
            generated_at=static.generated_at,
        )
