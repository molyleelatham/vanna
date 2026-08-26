"""System-level privacy, collusion, freshness, and oversight agent."""

from __future__ import annotations

from .contracts import GovernanceAssessment, GovernanceContext


class GovernanceAgent:
    name = "GovernanceAgent"

    def assess(self, context: GovernanceContext) -> GovernanceAssessment:
        reasons: list[str] = []

        if context.synchronized_routing_ratio >= 0.60:
            reasons.append("synchronized routing concentration exceeded the safe threshold")
        if context.rare_participant_query:
            reasons.append("request attempted to isolate rare participant behavior")
        if reasons:
            return GovernanceAssessment(
                action="SUPPRESS_COLLECTIVE_OUTPUT",
                reasons=reasons,
            )

        if context.anomalous_model_update:
            return GovernanceAssessment(
                action="HUMAN_REVIEW",
                reasons=["anomalous participant model update requires investigation"],
            )

        if (
            context.cohort_size < 3
            or context.recommendation.data_freshness_seconds > 900
        ):
            return GovernanceAssessment(
                action="USE_LOCAL_FALLBACK",
                reasons=["minimum cohort or evidence freshness control failed"],
            )

        if (
            context.recommendation.confidence == "low"
            or context.last_look.review_required
            or context.counterparty_risk.route_posture == "HUMAN_REVIEW"
            or context.margin.human_review_required
            or context.manipulation.human_review_required
        ):
            return GovernanceAssessment(
                action="HUMAN_REVIEW",
                reasons=["one or more independent agent review controls triggered"],
            )

        if (
            context.counterparty_risk.route_posture == "REDUCED_SIZE"
            or context.margin.pressure == "medium"
        ):
            return GovernanceAssessment(
                action="REDUCE_SIZE",
                reasons=["reliability or margin pressure calls for a smaller local route"],
            )

        return GovernanceAssessment(
            action="ALLOW_LOCAL_RECOMMENDATION",
            reasons=["all privacy, cohort, freshness, and agent controls passed"],
        )
