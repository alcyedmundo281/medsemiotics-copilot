"""Authorize one folder-backed Classroom material package without publishing it."""

from collections.abc import Collection

from medsemiotics.agents.framework import AgentCapabilityFramework
from medsemiotics.domain.agents import (
    AgentActionIntent,
    AgentAuthorizationContext,
    AgentPillar,
    AutonomyLevel,
)
from medsemiotics.domain.classroom_action import (
    ClassroomActionApproval,
    ClassroomActionDecision,
    ClassroomActionRecord,
    ClassroomActionStatus,
)
from medsemiotics.domain.classroom_material import ClassroomMaterialPackagePlan

CAPABILITY_ID = "coordination.classroom-material-publish"


class ClassroomMaterialPublishAuthorizer:
    """Bind named approval and persistent idempotency to one material package."""

    def __init__(self, capability_framework: AgentCapabilityFramework) -> None:
        self._framework = capability_framework

    def authorize(
        self,
        *,
        plan: ClassroomMaterialPackagePlan,
        approval: ClassroomActionApproval,
        applied_actions: Collection[ClassroomActionRecord] = (),
    ) -> ClassroomActionDecision:
        """Return authorized, denied, or already-applied without external access."""
        if approval.content_fingerprint != plan.content_fingerprint:
            return self._decision(
                plan,
                ClassroomActionStatus.DENIED,
                "The approval does not match the reviewed material package.",
            )

        capability = self._framework.evaluate(
            AgentActionIntent(
                agent=AgentPillar.COORDINATION,
                capability_id=CAPABILITY_ID,
                requested_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                requested_by=plan.prepared_by,
                rationale=f"Publish one material package for {plan.course_code} ({plan.topic_id}).",
            ),
            AgentAuthorizationContext(approved=True, approved_by=approval.approved_by),
        )
        if not capability.allowed:
            return self._decision(plan, ClassroomActionStatus.DENIED, capability.reason)

        existing = next(
            (record for record in applied_actions if record.identity_key == plan.identity_key),
            None,
        )
        if existing is not None:
            return self._decision(
                plan,
                ClassroomActionStatus.ALREADY_APPLIED,
                "This material package is already recorded; repeating it would duplicate the post.",
                existing_reference=existing.external_reference,
            )

        return self._decision(
            plan,
            ClassroomActionStatus.AUTHORIZED,
            f"One student-visible material package is approved by {approval.approved_by}.",
            approved_by=approval.approved_by,
        )

    @staticmethod
    def _decision(
        plan: ClassroomMaterialPackagePlan,
        status: ClassroomActionStatus,
        reason: str,
        *,
        approved_by: str | None = None,
        existing_reference: str | None = None,
    ) -> ClassroomActionDecision:
        return ClassroomActionDecision(
            status=status,
            action_type=plan.action_type,
            identity_key=plan.identity_key,
            approved_by=approved_by,
            existing_reference=existing_reference,
            reason=reason,
        )
