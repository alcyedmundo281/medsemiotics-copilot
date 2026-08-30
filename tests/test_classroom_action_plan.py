"""Tests for the Loop 0.6E Classroom action planner and authorizer."""

from datetime import UTC, date, datetime

import pytest

from medsemiotics.agents.framework import (
    AgentCapabilityFramework,
    build_default_agent_framework,
)
from medsemiotics.domain.agents import (
    AgentCapability,
    AgentPillar,
    AgentProfile,
    AutonomyLevel,
)
from medsemiotics.domain.classroom_action import (
    ClassroomActionApproval,
    ClassroomActionRecord,
    ClassroomActionStatus,
    ClassroomActionType,
)
from medsemiotics.domain.coordination_view import (
    AcademicProgressSummary,
    CalendarLink,
    CalendarLinkStatus,
    ClassroomLink,
    ClassroomLinkStatus,
    CoordinationReadiness,
    CourseCoordinationEntry,
)
from medsemiotics.domain.exceptions import (
    ClassroomActionAuthorizationError,
    ClassroomActionPlanError,
)
from medsemiotics.domain.external_courses import ExternalCourseLifecycle
from medsemiotics.services.classroom_action_plan import (
    CAPABILITY_ID,
    ClassroomActionAuthorizer,
    ClassroomActionPlanner,
)

PREPARED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def make_entry(**updates: object) -> CourseCoordinationEntry:
    """Build a coordination entry whose course is decisively linked to Classroom."""
    values: dict[str, object] = {
        "course_code": "NEURO",
        "course_name": "Semiología Neurológica",
        "classroom": ClassroomLink(
            status=ClassroomLinkStatus.LINKED,
            external_id="770001",
            display_name="Semiología Neurológica 2026-2",
            lifecycle=ExternalCourseLifecycle.ACTIVE,
            reason="Exactly one accessible Classroom course matches this course.",
        ),
        "calendar": CalendarLink(
            status=CalendarLinkStatus.CONFIGURED,
            calendar_id="neuro@group.calendar.google.com",
            reason="A calendar is bound and enabled for this course.",
        ),
        "academic": AcademicProgressSummary(
            total_topics=3,
            completed_topics=1,
            in_progress_topics=0,
            not_started_topics=2,
            skipped_topics=0,
            next_required_topic_id="neuro-02",
        ),
        "readiness": CoordinationReadiness.READY,
        "blockers": (),
    }
    values.update(updates)
    return CourseCoordinationEntry(**values)  # type: ignore[arg-type]


def make_planner() -> ClassroomActionPlanner:
    """Build the planner with a fixed clock."""
    return ClassroomActionPlanner(clock=lambda: PREPARED_AT)


def plan_draft(planner: ClassroomActionPlanner | None = None, **updates: object) -> object:
    """Plan one coursework draft with sensible defaults."""
    values: dict[str, object] = {
        "entry": make_entry(),
        "semester_id": "2026-2",
        "topic_id": "neuro-02",
        "title": "Taller de exploración de pares craneales",
        "prepared_by": "course-director",
        "instructions": "Revisar el caso clínico antes de la sesión.",
        "due_date": date(2026, 9, 12),
    }
    values.update(updates)
    return (planner or make_planner()).plan_coursework_draft(**values)  # type: ignore[arg-type]


class TestClassroomActionPlanner:
    """Verify a plan is only built from a decisive, teachable link."""

    def test_plans_one_coursework_draft(self) -> None:
        plan = plan_draft()

        assert plan.action_type is ClassroomActionType.CREATE_COURSEWORK_DRAFT  # type: ignore[attr-defined]
        assert plan.external_course_id == "770001"  # type: ignore[attr-defined]
        assert plan.course_code == "NEURO"  # type: ignore[attr-defined]
        assert plan.prepared_at == PREPARED_AT  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "link",
        [
            ClassroomLink(status=ClassroomLinkStatus.NOT_FOUND, reason="Nothing matched."),
            ClassroomLink(status=ClassroomLinkStatus.NOT_READ, reason="No snapshot supplied."),
            ClassroomLink(
                status=ClassroomLinkStatus.AMBIGUOUS,
                candidate_ids=("770001", "770002"),
                reason="Two courses matched.",
            ),
        ],
    )
    def test_refuses_a_course_without_a_decisive_link(self, link: ClassroomLink) -> None:
        entry = make_entry(
            classroom=link,
            readiness=CoordinationReadiness.PARTIAL,
            blockers=(f"classroom: {link.reason}",),
        )

        with pytest.raises(ClassroomActionPlanError) as err:
            plan_draft(entry=entry)

        assert "not decisively linked" in str(err.value)

    def test_refuses_a_link_without_a_classroom_course_id(self) -> None:
        entry = make_entry().model_copy(
            update={
                "classroom": ClassroomLink.model_construct(
                    status=ClassroomLinkStatus.LINKED,
                    external_id=None,
                    display_name="Semiología Neurológica",
                    lifecycle=ExternalCourseLifecycle.ACTIVE,
                    candidate_ids=(),
                    reason="Exactly one accessible Classroom course matches this course.",
                )
            }
        )

        with pytest.raises(ClassroomActionPlanError) as err:
            plan_draft(entry=entry)

        assert "without a Classroom course id" in str(err.value)

    def test_refuses_a_course_without_a_tracked_syllabus(self) -> None:
        entry = make_entry(
            academic=AcademicProgressSummary(
                total_topics=0,
                completed_topics=0,
                in_progress_topics=0,
                not_started_topics=0,
                skipped_topics=0,
            ),
            readiness=CoordinationReadiness.BLOCKED,
            blockers=("syllabus: no planned topics are tracked for this course.",),
        )

        with pytest.raises(ClassroomActionPlanError) as err:
            plan_draft(entry=entry)

        assert "no tracked syllabus topics" in str(err.value)

    def test_refuses_a_due_date_before_preparation(self) -> None:
        with pytest.raises(ClassroomActionPlanError) as err:
            plan_draft(due_date=date(2026, 8, 29))

        assert "before the plan preparation date" in str(err.value)

    def test_accepts_a_due_date_on_the_preparation_day(self) -> None:
        plan = plan_draft(due_date=date(2026, 8, 30))

        assert plan.due_date == date(2026, 8, 30)  # type: ignore[attr-defined]

    def test_wraps_invalid_content(self) -> None:
        with pytest.raises(ClassroomActionPlanError) as err:
            plan_draft(title="   ")

        assert "failed validation" in str(err.value)

    def test_rejects_a_naive_clock(self) -> None:
        planner = ClassroomActionPlanner(clock=lambda: datetime(2026, 8, 30, 12, 30))

        with pytest.raises(ClassroomActionPlanError):
            plan_draft(planner)


def make_approval(plan: object, **updates: object) -> ClassroomActionApproval:
    """Build a named approval bound to the reviewed plan content."""
    values: dict[str, object] = {
        "approved_by": "department-head",
        "approved_at": PREPARED_AT,
        "content_fingerprint": plan.content_fingerprint,  # type: ignore[attr-defined]
    }
    values.update(updates)
    return ClassroomActionApproval(**values)  # type: ignore[arg-type]


class TestClassroomActionAuthorizer:
    """Verify one approved action runs at most once, and never without approval."""

    def test_authorizes_an_approved_plan(self) -> None:
        plan = plan_draft()
        decision = ClassroomActionAuthorizer(build_default_agent_framework()).authorize(
            plan=plan,  # type: ignore[arg-type]
            approval=make_approval(plan),
        )

        assert decision.status is ClassroomActionStatus.AUTHORIZED
        assert decision.approved_by == "department-head"
        assert decision.identity_key == plan.identity_key  # type: ignore[attr-defined]
        assert decision.existing_reference is None

    def test_denies_an_approval_of_different_content(self) -> None:
        approved_plan = plan_draft()
        edited_plan = plan_draft(instructions="Instrucciones corregidas después de aprobar.")
        authorizer = ClassroomActionAuthorizer(build_default_agent_framework())

        decision = authorizer.evaluate(
            plan=edited_plan,  # type: ignore[arg-type]
            approval=make_approval(approved_plan),
        )

        assert decision.status is ClassroomActionStatus.DENIED
        assert "re-review" in decision.reason
        assert decision.approved_by is None

        with pytest.raises(ClassroomActionAuthorizationError):
            authorizer.authorize(
                plan=edited_plan,  # type: ignore[arg-type]
                approval=make_approval(approved_plan),
            )

    def test_is_idempotent_against_the_applied_ledger(self) -> None:
        plan = plan_draft()
        record = ClassroomActionRecord(
            identity_key=plan.identity_key,  # type: ignore[attr-defined]
            external_course_id="770001",
            applied_at=PREPARED_AT,
            applied_by="course-director",
            external_reference="coursework-991",
        )

        decision = ClassroomActionAuthorizer(build_default_agent_framework()).authorize(
            plan=plan,  # type: ignore[arg-type]
            approval=make_approval(plan),
            applied_actions=[record],
        )

        assert decision.status is ClassroomActionStatus.ALREADY_APPLIED
        assert decision.existing_reference == "coursework-991"
        assert decision.approved_by is None

    def test_repeats_only_for_the_same_identity(self) -> None:
        plan = plan_draft()
        other = ClassroomActionRecord(
            identity_key=plan_draft(title="Otro taller distinto").identity_key,  # type: ignore[attr-defined]
            external_course_id="770001",
            applied_at=PREPARED_AT,
            applied_by="course-director",
        )

        decision = ClassroomActionAuthorizer(build_default_agent_framework()).authorize(
            plan=plan,  # type: ignore[arg-type]
            approval=make_approval(plan),
            applied_actions=[other],
        )

        assert decision.status is ClassroomActionStatus.AUTHORIZED

    def test_edited_content_reuses_the_same_identity(self) -> None:
        applied = plan_draft()
        edited = plan_draft(instructions="Instrucciones corregidas.")
        record = ClassroomActionRecord(
            identity_key=applied.identity_key,  # type: ignore[attr-defined]
            external_course_id="770001",
            applied_at=PREPARED_AT,
            applied_by="course-director",
        )

        decision = ClassroomActionAuthorizer(build_default_agent_framework()).authorize(
            plan=edited,  # type: ignore[arg-type]
            approval=make_approval(edited),
            applied_actions=[record],
        )

        assert decision.status is ClassroomActionStatus.ALREADY_APPLIED

    def test_denies_an_action_outside_the_coursework_draft_contract(self) -> None:
        plan = plan_draft()
        forged = plan.model_copy(update={"action_type": "publish_grades"})  # type: ignore[attr-defined]

        with pytest.raises(ClassroomActionAuthorizationError) as err:
            ClassroomActionAuthorizer(build_default_agent_framework()).evaluate(
                plan=forged,
                approval=make_approval(plan),
            )

        assert "publish_grades" in str(err.value)

    def test_denies_when_the_capability_ceiling_forbids_execution(self) -> None:
        framework = AgentCapabilityFramework(
            profiles=[
                AgentProfile(
                    agent=AgentPillar.COORDINATION,
                    purpose="Observe Classroom actions without executing them.",
                    maximum_autonomy=AutonomyLevel.OBSERVE,
                    capabilities=[
                        AgentCapability(
                            capability_id=CAPABILITY_ID,
                            agent=AgentPillar.COORDINATION,
                            job="Review one proposed Classroom action.",
                            tools=["google-classroom:coursework-draft"],
                            categories=["planned action"],
                            output="Reviewed Classroom action proposal.",
                            boundary="Must not execute any Classroom write.",
                            minimum_autonomy=AutonomyLevel.OBSERVE,
                            maximum_autonomy=AutonomyLevel.OBSERVE,
                        )
                    ],
                )
            ]
        )
        plan = plan_draft()

        decision = ClassroomActionAuthorizer(framework).evaluate(
            plan=plan,  # type: ignore[arg-type]
            approval=make_approval(plan),
        )

        assert decision.status is ClassroomActionStatus.DENIED
        assert "ceiling" in decision.reason


class TestClassroomActionCapability:
    """Verify the declared capability keeps execution behind named approval."""

    def test_requires_approval_and_forbids_automation(self) -> None:
        capability = build_default_agent_framework().get_capability(
            AgentPillar.COORDINATION,
            CAPABILITY_ID,
        )

        assert capability.minimum_autonomy is AutonomyLevel.EXECUTE_WITH_APPROVAL
        assert capability.maximum_autonomy is AutonomyLevel.EXECUTE_WITH_APPROVAL
        assert capability.external_mutation is True
        assert capability.trusted_automation_eligible is False
