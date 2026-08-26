"""System-level privacy, collusion, freshness, and oversight agent."""

from __future__ import annotations

from ..connectors import ConnectorClient, FederationMetrics
from .contracts import GovernanceAssessment, GovernanceContext


class GovernanceAgent:
    name = "GovernanceAgent"

    def assess(
        self,
        context: GovernanceContext,
        connectors: ConnectorClient | None = None,
    ) -> GovernanceAssessment:
        # Enrich with live federation metrics if available
        if connectors is not None:
            try:
                fed = connectors.federation_metrics_or_fallback()
                cohort_size = fed.cohort_size
                anomalous_model_update = fed.anomalous_update_detected
                synchronized_routing_ratio = fed.synchronized_routing_ratio
            except Exception:
                cohort_size = context.cohort_size
                anomalous_model_update = context.anomalous_model_update
                synchronized_routing_ratio = context.synchronized_routing_ratio
        else:
            cohort_size = context.cohort_size
            anomalous_model_update = context.anomalous_model_update
            synchronized_routing_ratio = context.synchronized_routing_ratio

        reasons: list[str] = []

        if synchronized_routing_ratio >= 0.60:
            reasons.append("synchronized routing concentration exceeded the safe threshold")
        if context.rare_participant_query:
            reasons.append("request attempted to isolate rare participant behavior")
        if reasons:
            return GovernanceAssessment(
                action="SUPPRESS_COLLECTIVE_OUTPUT",
                reasons=reasons,
            )

        if anomalous_model_update:
            return GovernanceAssessment(
                action="HUMAN_REVIEW",
                reasons=["anomalous participant model update requires investigation"],
            )

        if (
            cohort_size < 3
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

    def explain(self, assessment: GovernanceAssessment) -> str:
        """Deterministic narration of the final governance decision."""
        return (
            f"Final decision {assessment.action}: {'; '.join(assessment.reasons)}. "
            "No automatic execution, blacklist, or collective instruction."
        )
