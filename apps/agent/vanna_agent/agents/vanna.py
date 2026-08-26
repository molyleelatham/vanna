"""Primary expected-execution-value agent."""

from __future__ import annotations

from datetime import datetime

from ..domain import OrderRequest, ProviderEvidence, Recommendation, recommend


class VannaAgent:
    name = "Vanna"

    def assess(
        self,
        order: OrderRequest,
        evidence: list[ProviderEvidence],
        *,
        now: datetime | None = None,
    ) -> Recommendation:
        return recommend(order, evidence, now=now)
