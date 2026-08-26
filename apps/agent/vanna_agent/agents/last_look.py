"""Conditional last-look behavior agent."""

from __future__ import annotations

from ..domain import OrderRequest, ProviderEvidence, last_look_signal
from .contracts import LastLookAssessment


class LastLookAgent:
    name = "LastLookAgent"

    def assess(
        self,
        order: OrderRequest,
        evidence: list[ProviderEvidence],
    ) -> LastLookAssessment:
        available = [item for item in evidence if item.provider in order.available_providers]
        if not available:
            raise ValueError("no last-look evidence for available providers")
        displayed_quote_leader = max(
            available,
            key=lambda item: item.displayed_price_benefit_bps,
        )
        return LastLookAssessment.model_validate(
            last_look_signal(displayed_quote_leader)
        )
