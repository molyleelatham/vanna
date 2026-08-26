"""Conditional last-look behavior agent."""

from __future__ import annotations

from ..connectors import ConnectorClient, OrderFlowStats
from ..domain import OrderRequest, ProviderEvidence, last_look_signal
from .contracts import LastLookAssessment


class LastLookAgent:
    name = "LastLookAgent"

    def assess(
        self,
        order: OrderRequest,
        evidence: list[ProviderEvidence],
        connectors: ConnectorClient | None = None,
    ) -> LastLookAssessment:
        available = [item for item in evidence if item.provider in order.available_providers]
        if not available:
            raise ValueError("no last-look evidence for available providers")
        displayed_quote_leader = max(
            available,
            key=lambda item: item.displayed_price_benefit_bps,
        )

        if connectors is None:
            return LastLookAssessment.model_validate(
                last_look_signal(displayed_quote_leader)
            )

        # Enrich with live order flow for the displayed-quote leader
        try:
            live_flow = connectors.order_flow_or_fallback(
                provider=displayed_quote_leader.provider,
                window="1h",
            )
            # Use live rejection asymmetry if available (more current)
            blended_asymmetry = 0.7 * displayed_quote_leader.rejection_asymmetry + 0.3 * live_flow.rejection_asymmetry
            blended_item = ProviderEvidence(
                provider=displayed_quote_leader.provider,
                sample_count=displayed_quote_leader.sample_count,
                fill_probability=displayed_quote_leader.fill_probability,
                rejection_probability=displayed_quote_leader.rejection_probability,
                expected_slippage_bps=displayed_quote_leader.expected_slippage_bps,
                expected_latency_ms=displayed_quote_leader.expected_latency_ms,
                displayed_price_benefit_bps=displayed_quote_leader.displayed_price_benefit_bps,
                rejection_asymmetry=blended_asymmetry,
                model_version=displayed_quote_leader.model_version,
                generated_at=displayed_quote_leader.generated_at,
            )
            return LastLookAssessment.model_validate(last_look_signal(blended_item))
        except Exception:
            return LastLookAssessment.model_validate(last_look_signal(displayed_quote_leader))
