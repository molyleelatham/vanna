"""Strict contracts for independently testable Vanna agent roles."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain import OrderRequest, Provider, Recommendation


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LastLookAssessment(StrictModel):
    provider: Provider
    rejection_asymmetry: float = Field(ge=-1, le=1)
    level: Literal["normal", "elevated"]
    review_required: bool
    explanation: str


class CounterpartyRiskAssessment(StrictModel):
    provider: Provider
    reliability_score: float = Field(ge=0, le=1)
    confidence: Literal["low", "medium", "high"]
    route_posture: Literal["NORMAL", "REDUCED_SIZE", "HUMAN_REVIEW"]
    factors: list[str]
    automatic_exclusion: Literal[False] = False


class MarginContext(StrictModel):
    pair: str
    volatility: Literal["calm", "normal", "high"]
    margin_utilization: float = Field(ge=0, le=1)
    leverage_ratio: float = Field(ge=0)
    correlated_exposure: float = Field(ge=0, le=1)
    settlement_pressure: float = Field(ge=0, le=1)


class MarginAssessment(StrictModel):
    pressure: Literal["low", "medium", "high"]
    recommended_size_multiplier: float = Field(ge=0, le=1)
    human_review_required: bool
    factors: list[str]
    automatic_liquidation: Literal[False] = False


class MarketPatternContext(StrictModel):
    provider: Provider
    quote_to_trade_ratio: float = Field(ge=0)
    cancellation_rate: float = Field(ge=0, le=1)
    synchronized_quote_score: float = Field(ge=0, le=1)
    cross_pair_anomaly_score: float = Field(ge=0, le=1)
    pre_movement_activity_score: float = Field(ge=0, le=1)
    sample_count: int = Field(ge=0)


class ManipulationAssessment(StrictModel):
    provider: Provider
    signal: Literal["normal", "watch", "review"]
    anomaly_score: float = Field(ge=0, le=1)
    human_review_required: bool
    factors: list[str]
    misconduct_finding: Literal[False] = False


class GovernanceContext(StrictModel):
    recommendation: Recommendation
    last_look: LastLookAssessment
    counterparty_risk: CounterpartyRiskAssessment
    margin: MarginAssessment
    manipulation: ManipulationAssessment
    cohort_size: int = Field(ge=0)
    synchronized_routing_ratio: float = Field(ge=0, le=1)
    rare_participant_query: bool = False
    anomalous_model_update: bool = False


class GovernanceAssessment(StrictModel):
    action: Literal[
        "ALLOW_LOCAL_RECOMMENDATION",
        "REDUCE_SIZE",
        "USE_LOCAL_FALLBACK",
        "HUMAN_REVIEW",
        "SUPPRESS_COLLECTIVE_OUTPUT",
    ]
    reasons: list[str]
    automatic_execution: Literal[False] = False
    automatic_blacklist: Literal[False] = False
    collective_instruction: Literal[False] = False


class AgentContribution(StrictModel):
    """One agent's visible contribution to the collaborative decision.

    Carries the deterministic narration plus the typed assessment payload so
    the orchestrator, AgentApp, and any LLM narrator all read the same handoff.
    """

    agent: str
    summary: str
    assessment: dict


class AgentBundleInput(StrictModel):
    order: OrderRequest
