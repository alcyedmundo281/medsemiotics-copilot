"""Tests for the Loop 0.6D coordination view service."""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from medsemiotics.agents.framework import (
    AgentCapabilityFramework,
    build_default_agent_framework,
)
from medsemiotics.domain.academic import Course, SemesterConfig
from medsemiotics.domain.academic_state import (
    CourseAcademicState,
    TopicProgress,
    TopicProgressStatus,
)
from medsemiotics.domain.agents import (
    AgentCapability,
    AgentPillar,
    AgentProfile,
    AutonomyLevel,
)
from medsemiotics.domain.calendar import CourseCalendarConfig
from medsemiotics.domain.coordination_view import (
    CalendarLinkStatus,
    ClassroomLinkStatus,
    CoordinationReadiness,
)
from medsemiotics.domain.exceptions import (
    AgentCapabilityConfigurationError,
    CoordinationViewError,
)
from medsemiotics.domain.external_courses import (
    ExternalCourse,
    ExternalCourseLifecycle,
    ExternalCourseProvider,
    ExternalCourseSnapshot,
)
from medsemiotics.services.coordination_view import CoordinationViewService
from medsemiotics.services.course_state_service import CourseStateService

SCOPE = "https://www.googleapis.com/auth/classroom.courses.readonly"
GENERATED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def make_semester(courses: list[Course] | None = None) -> SemesterConfig:
    """Build the tracked semester configuration."""
    return SemesterConfig(
        semester_id="2026-2",
        display_name="Semestre 2026-2",
        active=True,
        timezone="America/Guayaquil",
        courses=courses
        or [
            Course(code="NEURO", name="Semiología Neurológica"),
            Course(code="GASTRO", name="Gastroenterología Clínica"),
        ],
    )


def make_calendar_config(**updates: object) -> CourseCalendarConfig:
    """Build one tracked calendar binding."""
    values: dict[str, object] = {
        "semester_id": "2026-2",
        "course_code": "NEURO",
        "enabled": True,
        "calendar_id": "neuro@group.calendar.google.com",
        "aliases": ["Semiología Neurológica"],
    }
    values.update(updates)
    return CourseCalendarConfig(**values)  # type: ignore[arg-type]


def make_external(external_id: str, display_name: str) -> ExternalCourse:
    """Build one provider-neutral external course."""
    return ExternalCourse(
        provider=ExternalCourseProvider.GOOGLE_CLASSROOM,
        external_id=external_id,
        display_name=display_name,
        lifecycle=ExternalCourseLifecycle.ACTIVE,
    )


def make_snapshot(courses: list[ExternalCourse]) -> ExternalCourseSnapshot:
    """Build one private provider-neutral snapshot."""
    return ExternalCourseSnapshot(
        provider=ExternalCourseProvider.GOOGLE_CLASSROOM,
        captured_at=GENERATED_AT,
        requested_by="course-director",
        source_reference="AKfycb-deployment",
        approved_scopes=[SCOPE],
        courses=tuple(courses),
    )


def make_state(course_code: str, *, topic_count: int = 3) -> CourseAcademicState:
    """Build projected academic state with one completed and the rest pending topics."""
    topics = [
        TopicProgress(
            topic_id=f"{course_code.lower()}-{index:02d}",
            planned_order=index,
            required=True,
            status=(
                TopicProgressStatus.COMPLETED if index == 1 else TopicProgressStatus.NOT_STARTED
            ),
            session_count=1 if index == 1 else 0,
            first_taught_date=date(2026, 8, 10) if index == 1 else None,
            last_taught_date=date(2026, 8, 10) if index == 1 else None,
        )
        for index in range(1, topic_count + 1)
    ]
    return CourseAcademicState(semester_id="2026-2", course_code=course_code, topics=topics)


def make_state_service(
    states: dict[str, CourseAcademicState] | None = None,
) -> CourseStateService:
    """Build a read-only academic state source returning per-course projections."""
    service = MagicMock(spec=CourseStateService)
    resolved = states or {"NEURO": make_state("NEURO"), "GASTRO": make_state("GASTRO")}
    service.get_state.side_effect = lambda semester_id, course_code: resolved[  # noqa: ARG005
        course_code
    ]
    return service


def make_service(
    state_service: CourseStateService | None = None,
    framework: AgentCapabilityFramework | None = None,
) -> CoordinationViewService:
    """Build the coordination view service with a fixed clock."""
    return CoordinationViewService(
        capability_framework=framework or build_default_agent_framework(),
        course_state_service=state_service or make_state_service(),
        clock=lambda: GENERATED_AT,
    )


class TestCoordinationViewComposition:
    """Verify the view wires each course across Classroom, Calendar, and academic state."""

    def test_reports_a_fully_coordinated_course(self) -> None:
        view = make_service().build_view(
            semester=make_semester(),
            calendar_configs=[
                make_calendar_config(),
                make_calendar_config(
                    course_code="GASTRO",
                    calendar_id="gastro@group.calendar.google.com",
                    aliases=["Gastroenterología Clínica"],
                ),
            ],
            snapshot=make_snapshot(
                [
                    make_external("770001", "Semiología Neurológica 2026-2"),
                    make_external("770002", "Gastroenterología Clínica — grupo A"),
                ]
            ),
            requested_by="course-director",
        )

        assert view.semester_id == "2026-2"
        assert view.generated_at == GENERATED_AT
        assert [entry.course_code for entry in view.entries] == ["GASTRO", "NEURO"]

        neuro = view.entries[1]
        assert neuro.classroom.status is ClassroomLinkStatus.LINKED
        assert neuro.classroom.external_id == "770001"
        assert neuro.classroom.lifecycle is ExternalCourseLifecycle.ACTIVE
        assert neuro.calendar.status is CalendarLinkStatus.CONFIGURED
        assert neuro.academic.total_topics == 3
        assert neuro.academic.completed_topics == 1
        assert neuro.academic.next_required_topic_id == "neuro-02"
        assert neuro.readiness is CoordinationReadiness.READY
        assert neuro.blockers == ()
        assert view.unmatched_external_courses == ()

    def test_matches_through_a_configured_calendar_alias(self) -> None:
        view = make_service().build_view(
            semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
            calendar_configs=[make_calendar_config(aliases=["Neuro Semiologia", "Semio"])],
            snapshot=make_snapshot([make_external("770001", "NEURO SEMIOLOGIA — 2026-2")]),
            requested_by="course-director",
        )

        assert view.entries[0].classroom.status is ClassroomLinkStatus.LINKED

    def test_does_not_match_a_partial_word(self) -> None:
        view = make_service().build_view(
            semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
            calendar_configs=[make_calendar_config(aliases=["Neuro"])],
            snapshot=make_snapshot([make_external("770001", "Neurogastroenterología aplicada")]),
            requested_by="course-director",
        )

        entry = view.entries[0]
        assert entry.classroom.status is ClassroomLinkStatus.NOT_FOUND
        assert entry.readiness is CoordinationReadiness.PARTIAL
        assert any(blocker.startswith("classroom:") for blocker in entry.blockers)
        assert [course.external_id for course in view.unmatched_external_courses] == ["770001"]

    def test_does_not_match_a_name_shorter_than_the_course_label(self) -> None:
        view = make_service().build_view(
            semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
            calendar_configs=[make_calendar_config(aliases=["Semiología Neurológica Avanzada"])],
            snapshot=make_snapshot([make_external("770001", "Semiología")]),
            requested_by="course-director",
        )

        assert view.entries[0].classroom.status is ClassroomLinkStatus.NOT_FOUND

    def test_reports_ambiguity_instead_of_guessing(self) -> None:
        view = make_service().build_view(
            semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
            calendar_configs=[make_calendar_config()],
            snapshot=make_snapshot(
                [
                    make_external("770001", "Semiología Neurológica grupo A"),
                    make_external("770002", "Semiología Neurológica grupo B"),
                ]
            ),
            requested_by="course-director",
        )

        entry = view.entries[0]
        assert entry.classroom.status is ClassroomLinkStatus.AMBIGUOUS
        assert entry.classroom.candidate_ids == ("770001", "770002")
        assert entry.classroom.external_id is None
        assert len(view.unmatched_external_courses) == 2

    def test_reports_ambiguity_when_one_course_matches_two_tracked_courses(self) -> None:
        view = make_service().build_view(
            semester=make_semester(
                [
                    Course(code="NEURO", name="Semiología"),
                    Course(code="GASTRO", name="Semiología"),
                ]
            ),
            calendar_configs=[],
            snapshot=make_snapshot([make_external("770001", "Semiología integrada")]),
            requested_by="course-director",
        )

        assert {entry.classroom.status for entry in view.entries} == {ClassroomLinkStatus.AMBIGUOUS}
        assert [course.external_id for course in view.unmatched_external_courses] == ["770001"]

    def test_marks_classroom_as_not_read_without_a_snapshot(self) -> None:
        view = make_service().build_view(
            semester=make_semester(),
            calendar_configs=[make_calendar_config()],
            snapshot=None,
            requested_by="course-director",
        )

        assert {entry.classroom.status for entry in view.entries} == {ClassroomLinkStatus.NOT_READ}
        assert view.unmatched_external_courses == ()

    @pytest.mark.parametrize(
        ("config_updates", "expected_status"),
        [
            ({"enabled": False, "calendar_id": None}, CalendarLinkStatus.DISABLED),
            ({"enabled": False}, CalendarLinkStatus.DISABLED),
        ],
    )
    def test_reports_a_disabled_calendar_binding(
        self,
        config_updates: dict[str, object],
        expected_status: CalendarLinkStatus,
    ) -> None:
        view = make_service().build_view(
            semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
            calendar_configs=[make_calendar_config(**config_updates)],
            snapshot=make_snapshot([make_external("770001", "Semiología Neurológica")]),
            requested_by="course-director",
        )

        entry = view.entries[0]
        assert entry.calendar.status is expected_status
        assert entry.readiness is CoordinationReadiness.PARTIAL
        assert any(blocker.startswith("calendar:") for blocker in entry.blockers)

    def test_reports_a_missing_calendar_binding(self) -> None:
        view = make_service().build_view(
            semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
            calendar_configs=[],
            snapshot=make_snapshot([make_external("770001", "Semiología Neurológica")]),
            requested_by="course-director",
        )

        entry = view.entries[0]
        assert entry.calendar.status is CalendarLinkStatus.MISSING
        assert entry.calendar.calendar_id is None

    def test_blocks_a_course_without_planned_topics(self) -> None:
        empty_state = CourseAcademicState(semester_id="2026-2", course_code="NEURO", topics=[])
        view = make_service(make_state_service({"NEURO": empty_state})).build_view(
            semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
            calendar_configs=[make_calendar_config()],
            snapshot=make_snapshot([make_external("770001", "Semiología Neurológica")]),
            requested_by="course-director",
        )

        entry = view.entries[0]
        assert entry.readiness is CoordinationReadiness.BLOCKED
        assert entry.blockers == ("syllabus: no planned topics are tracked for this course.",)
        assert view.blocked_courses == (entry,)

    def test_excludes_and_records_inactive_courses(self) -> None:
        view = make_service(make_state_service({"NEURO": make_state("NEURO")})).build_view(
            semester=make_semester(
                [
                    Course(code="NEURO", name="Semiología Neurológica"),
                    Course(code="GASTRO", name="Gastroenterología Clínica", active=False),
                ]
            ),
            calendar_configs=[make_calendar_config()],
            snapshot=make_snapshot([make_external("770001", "Semiología Neurológica")]),
            requested_by="course-director",
        )

        assert [entry.course_code for entry in view.entries] == ["NEURO"]
        assert view.inactive_course_codes == ("GASTRO",)


class TestCoordinationViewFailsClosed:
    """Verify the view refuses inconsistent scopes and unauthorized intents."""

    def test_rejects_calendar_configuration_from_another_semester(self) -> None:
        with pytest.raises(CoordinationViewError) as err:
            make_service().build_view(
                semester=make_semester(),
                calendar_configs=[make_calendar_config(semester_id="2026-1")],
                snapshot=None,
                requested_by="course-director",
            )

        assert "2026-1" in str(err.value)

    def test_rejects_duplicate_calendar_configuration(self) -> None:
        with pytest.raises(CoordinationViewError):
            make_service().build_view(
                semester=make_semester(),
                calendar_configs=[make_calendar_config(), make_calendar_config()],
                snapshot=None,
                requested_by="course-director",
            )

    def test_rejects_academic_state_from_another_scope(self) -> None:
        foreign = CourseAcademicState(
            semester_id="2026-2",
            course_code="GASTRO",
            topics=make_state("GASTRO").topics,
        )

        with pytest.raises(CoordinationViewError) as err:
            make_service(make_state_service({"NEURO": foreign})).build_view(
                semester=make_semester([Course(code="NEURO", name="Semiología Neurológica")]),
                calendar_configs=[make_calendar_config()],
                snapshot=None,
                requested_by="course-director",
            )

        assert "does not match" in str(err.value)

    def test_requires_the_registered_coordination_capability(self) -> None:
        state_service = make_state_service()
        framework = AgentCapabilityFramework(
            profiles=[
                AgentProfile(
                    agent=AgentPillar.COORDINATION,
                    purpose="Align academic state without the coordination view.",
                    maximum_autonomy=AutonomyLevel.OBSERVE,
                    capabilities=[
                        AgentCapability(
                            capability_id="coordination.daily-brief",
                            agent=AgentPillar.COORDINATION,
                            job="Prepare a prioritized daily academic coordination brief.",
                            tools=["academic-state:read"],
                            categories=["priorities"],
                            output="Structured daily coordination brief.",
                            boundary="Must not create, move, or delete calendar events.",
                            minimum_autonomy=AutonomyLevel.OBSERVE,
                            maximum_autonomy=AutonomyLevel.OBSERVE,
                        )
                    ],
                )
            ]
        )

        with pytest.raises(AgentCapabilityConfigurationError):
            make_service(state_service, framework).build_view(
                semester=make_semester(),
                calendar_configs=[],
                snapshot=None,
                requested_by="course-director",
            )

        state_service.get_state.assert_not_called()  # type: ignore[attr-defined]

    def test_rejects_a_naive_clock(self) -> None:
        service = CoordinationViewService(
            capability_framework=build_default_agent_framework(),
            course_state_service=make_state_service(),
            clock=lambda: datetime(2026, 8, 30, 12, 30),
        )

        with pytest.raises(CoordinationViewError):
            service.build_view(
                semester=make_semester(),
                calendar_configs=[],
                snapshot=None,
                requested_by="course-director",
            )


class TestCoordinationCapability:
    """Verify the declared capability stays observation-only."""

    def test_is_registered_as_observe_only(self) -> None:
        capability = build_default_agent_framework().get_capability(
            AgentPillar.COORDINATION,
            "coordination.course-coordination-view",
        )

        assert capability.minimum_autonomy is AutonomyLevel.OBSERVE
        assert capability.maximum_autonomy is AutonomyLevel.OBSERVE
        assert capability.external_mutation is False
        assert capability.trusted_automation_eligible is False
