"""Stable agent interfaces for SuperGrid wiring.

Main-branch agents already implement these method names. Prompt aliases
recommend / analyse / review map to assess() so a later merge is a class
swap, not a rename.

TODO(merge): import replacement implementations here if main moves modules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..domain import OrderRequest, ProviderEvidence, Recommendation
from .contracts import (
    CounterpartyRiskAssessment,
    GovernanceAssessment,
    GovernanceContext,
    LastLookAssessment,
    ManipulationAssessment,
    MarginAssessment,
    MarginContext,
    MarketPatternContext,
)


class VannaLike(Protocol):
    name: str

    def assess(
        self,
        order: OrderRequest,
        evidence: list[ProviderEvidence],
        *,
        now: datetime | None = None,
    ) -> Recommendation: ...


class LastLookLike(Protocol):
    name: str

    def assess(
        self,
        order: OrderRequest,
        evidence: list[ProviderEvidence],
    ) -> LastLookAssessment: ...


class CounterpartyRiskLike(Protocol):
    name: str

    def assess(
        self,
        recommendation: Recommendation,
        evidence: list[ProviderEvidence],
    ) -> CounterpartyRiskAssessment: ...


class MarginLike(Protocol):
    name: str

    def assess(self, context: MarginContext) -> MarginAssessment: ...


class ManipulationWatchLike(Protocol):
    name: str

    def assess(self, context: MarketPatternContext) -> ManipulationAssessment: ...


class GovernanceLike(Protocol):
    name: str

    def assess(self, context: GovernanceContext) -> GovernanceAssessment: ...


HANDOFF_CHAIN = (
    "Vanna",
    "LastLookAgent",
    "CounterpartyRiskAgent",
    "MarginAgent",
    "ManipulationWatch",
    "GovernanceAgent",
)
