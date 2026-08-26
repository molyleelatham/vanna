"""Safety policy for locally owned Vanna recommendations."""

from __future__ import annotations

from .schemas import GovernanceDecision, LastLookSignal, Recommendation


def evaluate_governance(
    recommendation: Recommendation,
    last_look: LastLookSignal,
    *,
    cohort_size: int,
    minimum_cohort: int = 3,
) -> GovernanceDecision:
    reasons: list[str] = []
    action = "ALLOW_LOCAL_RECOMMENDATION"

    if cohort_size < minimum_cohort:
        action = "USE_LOCAL_FALLBACK"
        reasons.append("minimum collaborative cohort not met")
    if recommendation.data_freshness_seconds > 900:
        action = "USE_LOCAL_FALLBACK"
        reasons.append("shared evidence is stale")
    if recommendation.confidence == "low" or last_look.review_required:
        action = "HUMAN_REVIEW"
        reasons.append("low confidence or elevated last-look review signal")
    if not reasons:
        reasons.append("cohort, freshness, and confidence controls passed")

    return GovernanceDecision(action=action, reasons=reasons)
