"""Plan and authorize exactly one explicitly approved, idempotent Classroom action."""

from collections.abc import Callable, Collection
from datetime import UTC, date, datetime

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
    ClassroomActionPlan,
    ClassroomActionRecord,
    ClassroomActionStatus,
    ClassroomActionType,
)
from medsemiotics.domain.coordination_view import (
    ClassroomLinkStatus,
    CoordinationReadiness,
    CourseCoordinationEntry,
)
from medsemiotics.domain.exceptions import (
    ClassroomActionAuthorizationError,
    ClassroomActionPlanError,
)

CAPABILITY_ID = "coordination.classroom-action"

ALLOWED_ACTION_VALUES = (ClassroomActionType.CREATE_COURSEWORK_DRAFT.value,)


class ClassroomActionPlanner:
    """Build one reviewable Classroom action plan from a decisive coordination link."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        """Initialize the planner with an injectable clock."""
        self._clock = clock or (lambda: datetime.now(UTC))

    def plan_coursework_draft(
        self,
        *,
        entry: CourseCoordinationEntry,
        semester_id: str,
        topic_id: str,
        title: str,
        prepared_by: str,
        instructions: str | None = None,
        due_date: date | None = None,
    ) -> ClassroomActionPlan:
        """Describe one coursework draft for a course that is decisively linked to Classroom.

        Args:
            entry: Coordination entry carrying the Classroom binding for this course.
            semester_id: Academic semester of the target course.
            topic_id: Tracked syllabus topic the work belongs to.
            title: Coursework title shown to teachers while the item stays a draft.
            prepared_by: Accountable author of the plan.
            instructions: Optional coursework instructions.
            due_date: Optional local due date, never before the preparation date.

        Returns:
            One ClassroomActionPlan; a batch is not representable.

        Raises:
            ClassroomActionPlanError: If the course is not decisively linked, has no tracked
                syllabus, or the requested content is inconsistent.
        """
        if entry.classroom.status is not ClassroomLinkStatus.LINKED:
            msg = (
                f"Course '{entry.course_code}' is not decisively linked to a Classroom course "
                f"({entry.classroom.status.value}): {entry.classroom.reason}"
            )
            raise ClassroomActionPlanError(msg)

        external_course_id = entry.classroom.external_id
        if external_course_id is None:
            msg = f"Course '{entry.course_code}' has a link without a Classroom course id."
            raise ClassroomActionPlanError(msg)

        if entry.readiness is CoordinationReadiness.BLOCKED:
            msg = (
                f"Course '{entry.course_code}' has no tracked syllabus topics; coursework cannot "
                "be planned for it."
            )
            raise ClassroomActionPlanError(msg)

        prepared_at = self._prepared_at()
        if due_date is not None and due_date < prepared_at.date():
            msg = f"due_date {due_date} is before the plan preparation date."
            raise ClassroomActionPlanError(msg)

        try:
            return ClassroomActionPlan(
                action_type=ClassroomActionType.CREATE_COURSEWORK_DRAFT,
                semester_id=semester_id,
                course_code=entry.course_code,
                external_course_id=external_course_id,
                topic_id=topic_id,
                title=title,
                instructions=instructions,
                due_date=due_date,
                prepared_by=prepared_by,
                prepared_at=prepared_at,
            )
        except ValueError as err:
            msg = f"Classroom action plan failed validation: {err}"
            raise ClassroomActionPlanError(msg) from err

    def _prepared_at(self) -> datetime:
        """Obtain a timezone-aware preparation timestamp."""
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
            msg = "Classroom action planner clock must return a timezone-aware timestamp"
            raise ClassroomActionPlanError(msg)
        return timestamp


class ClassroomActionAuthorizer:
    """Decide whether one planned Classroom action may run, without running anything."""

    def __init__(self, capability_framework: AgentCapabilityFramework) -> None:
        """Initialize with the four-C capability registry."""
        self._capability_framework = capability_framework

    def evaluate(
        self,
        *,
        plan: ClassroomActionPlan,
        approval: ClassroomActionApproval,
        applied_actions: Collection[ClassroomActionRecord] = (),
    ) -> ClassroomActionDecision:
        """Evaluate one plan against its approval and MedSemiotics' applied-action ledger.

        Args:
            plan: The single action being considered.
            approval: Named approval bound to the reviewed content.
            applied_actions: Actions MedSemiotics already applied; Classroom is never queried,
                because coursework reads are outside the authorized scope.

        Returns:
            Explainable ClassroomActionDecision; no external system is contacted.

        Raises:
            ClassroomActionAuthorizationError: If the plan declares an action outside the
                permitted coursework-draft contract.
        """
        declared_action = str(plan.action_type)
        if declared_action not in ALLOWED_ACTION_VALUES:
            msg = (
                f"Action '{declared_action}' is outside the permitted coursework-draft "
                "contract and cannot be evaluated."
            )
            raise ClassroomActionAuthorizationError(msg)

        if approval.content_fingerprint != plan.content_fingerprint:
            return self._decision(
                plan,
                status=ClassroomActionStatus.DENIED,
                reason=(
                    "The approval does not match the plan content that was reviewed; "
                    "re-review the edited plan."
                ),
            )

        capability_decision = self._capability_framework.evaluate(
            AgentActionIntent(
                agent=AgentPillar.COORDINATION,
                capability_id=CAPABILITY_ID,
                requested_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                requested_by=plan.prepared_by,
                rationale=(
                    f"Create one Classroom coursework draft for {plan.course_code} "
                    f"({plan.topic_id})."
                ),
            ),
            AgentAuthorizationContext(approved=True, approved_by=approval.approved_by),
        )
        if not capability_decision.allowed:
            return self._decision(
                plan,
                status=ClassroomActionStatus.DENIED,
                reason=capability_decision.reason,
            )

        existing = next(
            (record for record in applied_actions if record.identity_key == plan.identity_key),
            None,
        )
        if existing is not None:
            return self._decision(
                plan,
                status=ClassroomActionStatus.ALREADY_APPLIED,
                reason=(
                    f"This action was already applied by {existing.applied_by} on "
                    f"{existing.applied_at.isoformat()}; repeating it would duplicate the draft."
                ),
                existing_reference=existing.external_reference,
            )

        return self._decision(
            plan,
            status=ClassroomActionStatus.AUTHORIZED,
            reason=(
                f"One coursework draft is authorized by {approval.approved_by} for the reviewed "
                "content."
            ),
            approved_by=approval.approved_by,
        )

    def authorize(
        self,
        *,
        plan: ClassroomActionPlan,
        approval: ClassroomActionApproval,
        applied_actions: Collection[ClassroomActionRecord] = (),
    ) -> ClassroomActionDecision:
        """Return an actionable decision or fail before any adapter could run.

        Args:
            plan: The single action being considered.
            approval: Named approval bound to the reviewed content.
            applied_actions: Actions MedSemiotics already applied.

        Returns:
            An AUTHORIZED or ALREADY_APPLIED decision.

        Raises:
            ClassroomActionAuthorizationError: If the action is denied or outside the
                permitted coursework-draft contract.
        """
        decision = self.evaluate(
            plan=plan,
            approval=approval,
            applied_actions=applied_actions,
        )
        if decision.status is ClassroomActionStatus.DENIED:
            msg = f"Classroom action denied for '{plan.course_code}': {decision.reason}"
            raise ClassroomActionAuthorizationError(msg)
        return decision

    @staticmethod
    def _decision(
        plan: ClassroomActionPlan,
        *,
        status: ClassroomActionStatus,
        reason: str,
        approved_by: str | None = None,
        existing_reference: str | None = None,
    ) -> ClassroomActionDecision:
        """Build a consistent immutable decision."""
        return ClassroomActionDecision(
            status=status,
            action_type=plan.action_type,
            identity_key=plan.identity_key,
            approved_by=approved_by,
            existing_reference=existing_reference,
            reason=reason,
        )
