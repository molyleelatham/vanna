"""Self-contained, FAB-safe Vanna decision and governance domain."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Provider = Literal["LP_A", "LP_B", "LP_C"]


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
    def unique_providers(cls, value: list[Provider]) -> list[Provider]:
        if len(value) != len(set(value)):
            raise ValueError("available_providers must be unique")
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
    expected_fill_probability: float
    confidence: Literal["low", "medium", "high"]
    reason: str
    model_version: str
    data_freshness_seconds: int


def execution_cost(item: ProviderEvidence) -> float:
    return round(
        item.expected_slippage_bps
        + item.rejection_probability * 2.5
        + item.expected_latency_ms / 100
        + (1 - item.fill_probability) * 2
        - item.displayed_price_benefit_bps,
        4,
    )


def recommend(
    order: OrderRequest,
    evidence: list[ProviderEvidence],
    *,
    now: datetime | None = None,
) -> Recommendation:
    choices = [item for item in evidence if item.provider in order.available_providers]
    if not choices:
        raise ValueError("no approved evidence for available providers")
    selected = min(choices, key=execution_cost)
    current = now or datetime.now(UTC)
    timestamp = selected.generated_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    freshness = max(0, int((current - timestamp).total_seconds()))
    confidence = (
        "high"
        if selected.sample_count >= 200 and freshness <= 900
        else "medium"
        if selected.sample_count >= 50 and freshness <= 3600
        else "low"
    )
    cost = execution_cost(selected)
    return Recommendation(
        provider=selected.provider,
        expected_cost_bps=cost,
        expected_fill_probability=selected.fill_probability,
        confidence=confidence,
        reason=(
            f"{selected.provider} has the lowest estimated executable cost ({cost:.2f} bps), "
            "including fill, rejection, slippage, and latency effects."
        ),
        model_version=selected.model_version,
        data_freshness_seconds=freshness,
    )


def last_look_signal(item: ProviderEvidence) -> dict[str, object]:
    elevated = item.rejection_asymmetry >= 0.15
    return {
        "provider": item.provider,
        "rejection_asymmetry": item.rejection_asymmetry,
        "level": "elevated" if elevated else "normal",
        "review_required": elevated,
        "explanation": (
            "Conditional rejection asymmetry is elevated; this is a review signal, "
            "not proof of misconduct."
            if elevated
            else "No elevated conditional rejection asymmetry was observed."
        ),
    }


def govern(
    recommendation: Recommendation,
    signal: dict[str, object],
    *,
    cohort_size: int,
) -> dict[str, object]:
    reasons: list[str] = []
    action = "ALLOW_LOCAL_RECOMMENDATION"
    if cohort_size < 3 or recommendation.data_freshness_seconds > 900:
        action = "USE_LOCAL_FALLBACK"
        reasons.append("cohort or freshness control failed")
    if recommendation.confidence == "low" or bool(signal["review_required"]):
        action = "HUMAN_REVIEW"
        reasons.append("confidence or last-look review control triggered")
    if not reasons:
        reasons.append("cohort, freshness, and confidence controls passed")
    return {
        "action": action,
        "reasons": reasons,
        "automatic_execution": False,
        "automatic_blacklist": False,
    }
