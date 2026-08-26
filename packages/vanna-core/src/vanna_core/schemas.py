"""Typed records crossing Vanna's privacy and agent boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Provider = Literal["LP_A", "LP_B", "LP_C"]
Confidence = Literal["low", "medium", "high"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderRequest(StrictModel):
    pair: str = Field(pattern=r"^[A-Z]{3}/[A-Z]{3}$")
    side: Literal["BUY", "SELL"]
    size_bucket: Literal["<1m", "1m-5m", "5m-10m", ">10m"]
    volatility: Literal["calm", "normal", "high"]
    available_providers: list[Provider] = Field(min_length=1)

    @field_validator("available_providers")
    @classmethod
    def providers_are_unique(cls, value: list[Provider]) -> list[Provider]:
        if len(value) != len(set(value)):
            raise ValueError("available_providers must not contain duplicates")
        return value


class ProviderEvidence(StrictModel):
    provider: Provider
    sample_count: int = Field(ge=0)
    fill_probability: float = Field(ge=0, le=1)
    rejection_probability: float = Field(ge=0, le=1)
    expected_slippage_bps: float = Field(ge=0)
    expected_latency_ms: float = Field(ge=0)
    displayed_price_benefit_bps: float
    rejection_asymmetry: float = Field(ge=-1, le=1)
    model_version: str
    generated_at: datetime


class Recommendation(StrictModel):
    provider: Provider
    expected_cost_bps: float
    expected_fill_probability: float = Field(ge=0, le=1)
    confidence: Confidence
    reason: str
    model_version: str
    data_freshness_seconds: int = Field(ge=0)


class AgentHandoff(StrictModel):
    order: OrderRequest
    recommendation: Recommendation
    approved_fields: tuple[str, ...] = (
        "pair",
        "side",
        "size_bucket",
        "volatility",
        "provider",
        "expected_cost_bps",
        "expected_fill_probability",
        "confidence",
        "model_version",
        "data_freshness_seconds",
    )


class LastLookSignal(StrictModel):
    provider: Provider
    rejection_asymmetry: float = Field(ge=-1, le=1)
    level: Literal["normal", "elevated"]
    review_required: bool
    explanation: str


class GovernanceDecision(StrictModel):
    action: Literal["ALLOW_LOCAL_RECOMMENDATION", "USE_LOCAL_FALLBACK", "HUMAN_REVIEW"]
    reasons: list[str]
    automatic_execution: Literal[False] = False
    automatic_blacklist: Literal[False] = False
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
