"""Tests for the Loop 0.6D coordination view domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from medsemiotics.domain.coordination_view import (
    AcademicProgressSummary,
    CalendarLink,
    CalendarLinkStatus,
    ClassroomLink,
    ClassroomLinkStatus,
    CoordinationReadiness,
    CoordinationView,
    CourseCoordinationEntry,
)
from medsemiotics.domain.external_courses import ExternalCourseLifecycle

GENERATED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def make_classroom_link(**updates: object) -> ClassroomLink:
    """Build a decisive Classroom binding."""
    values: dict[str, object] = {
        "status": ClassroomLinkStatus.LINKED,
        "external_id": "770001",
        "display_name": "Semiología Neurológica",
        "lifecycle": ExternalCourseLifecycle.ACTIVE,
        "reason": "Exactly one accessible Classroom course matches this course.",
    }
    values.update(updates)
    return ClassroomLink(**values)  # type: ignore[arg-type]


def make_calendar_link(**updates: object) -> CalendarLink:
    """Build a configured Calendar binding."""
    values: dict[str, object] = {
        "status": CalendarLinkStatus.CONFIGURED,
        "calendar_id": "neuro@group.calendar.google.com",
        "reason": "A calendar is bound and enabled for this course.",
    }
    values.update(updates)
    return CalendarLink(**values)  # type: ignore[arg-type]


def make_summary(**updates: object) -> AcademicProgressSummary:
    """Build a consistent academic progress summary."""
    values: dict[str, object] = {
        "total_topics": 4,
        "completed_topics": 1,
        "in_progress_topics": 1,
        "not_started_topics": 2,
        "skipped_topics": 0,
        "next_required_topic_id": "neuro-02",
    }
    values.update(updates)
    return AcademicProgressSummary(**values)  # type: ignore[arg-type]


def make_entry(**updates: object) -> CourseCoordinationEntry:
    """Build a fully coordinated course entry."""
    values: dict[str, object] = {
        "course_code": "NEURO",
        "course_name": "Semiología Neurológica",
        "classroom": make_classroom_link(),
        "calendar": make_calendar_link(),
        "academic": make_summary(),
        "readiness": CoordinationReadiness.READY,
        "blockers": (),
    }
    values.update(updates)
    return CourseCoordinationEntry(**values)  # type: ignore[arg-type]


def make_view(**updates: object) -> CoordinationView:
    """Build a coordination view with deterministic provenance."""
    values: dict[str, object] = {
        "semester_id": "2026-2",
        "generated_at": GENERATED_AT,
        "requested_by": "course-director",
        "entries": (make_entry(),),
    }
    values.update(updates)
    return CoordinationView(**values)  # type: ignore[arg-type]


class TestClassroomLink:
    """Verify a binding never claims evidence it does not have."""

    def test_requires_metadata_for_a_linked_course(self) -> None:
        with pytest.raises(ValidationError):
            make_classroom_link(external_id=None)

        with pytest.raises(ValidationError):
            make_classroom_link(lifecycle=None)

    def test_rejects_leftover_candidates_on_a_linked_course(self) -> None:
        with pytest.raises(ValidationError):
            make_classroom_link(candidate_ids=("770001", "770002"))

    @pytest.mark.parametrize(
        "status",
        [
            ClassroomLinkStatus.NOT_FOUND,
            ClassroomLinkStatus.NOT_READ,
        ],
    )
    def test_undecided_statuses_carry_no_course_metadata(
        self,
        status: ClassroomLinkStatus,
    ) -> None:
        link = ClassroomLink(status=status, reason="Nothing matched.")

        assert link.external_id is None
        assert link.lifecycle is None

        with pytest.raises(ValidationError):
            ClassroomLink(status=status, external_id="770001", reason="Nothing matched.")

        with pytest.raises(ValidationError):
            ClassroomLink(
                status=status,
                lifecycle=ExternalCourseLifecycle.ACTIVE,
                reason="Nothing matched.",
            )

    def test_ambiguous_requires_candidates(self) -> None:
        with pytest.raises(ValidationError):
            ClassroomLink(status=ClassroomLinkStatus.AMBIGUOUS, reason="Two courses matched.")

        link = ClassroomLink(
            status=ClassroomLinkStatus.AMBIGUOUS,
            candidate_ids=("770001", "770002"),
            reason="Two courses matched.",
        )

        assert link.candidate_ids == ("770001", "770002")

    def test_requires_a_reason(self) -> None:
        with pytest.raises(ValidationError):
            make_classroom_link(reason="   ")


class TestCalendarLink:
    """Verify only a configured binding names a calendar."""

    def test_configured_requires_a_calendar_id(self) -> None:
        with pytest.raises(ValidationError):
            make_calendar_link(calendar_id=None)

    def test_missing_must_not_name_a_calendar(self) -> None:
        with pytest.raises(ValidationError):
            make_calendar_link(status=CalendarLinkStatus.MISSING)

    def test_disabled_may_retain_the_configured_calendar(self) -> None:
        link = make_calendar_link(
            status=CalendarLinkStatus.DISABLED,
            reason="The tracked calendar binding is disabled.",
        )

        assert link.calendar_id == "neuro@group.calendar.google.com"


class TestAcademicProgressSummary:
    """Verify topic counts stay internally consistent."""

    def test_rejects_counts_that_do_not_sum_to_the_total(self) -> None:
        with pytest.raises(ValidationError):
            make_summary(completed_topics=3)

    def test_accepts_a_course_without_topics(self) -> None:
        summary = make_summary(
            total_topics=0,
            completed_topics=0,
            in_progress_topics=0,
            not_started_topics=0,
            skipped_topics=0,
            next_required_topic_id=None,
        )

        assert summary.total_topics == 0

    def test_rejects_negative_counts(self) -> None:
        with pytest.raises(ValidationError):
            make_summary(skipped_topics=-1)


class TestCourseCoordinationEntry:
    """Verify readiness always agrees with the recorded blockers."""

    def test_ready_must_not_list_blockers(self) -> None:
        with pytest.raises(ValidationError):
            make_entry(blockers=("calendar: missing",))

    @pytest.mark.parametrize(
        "readiness",
        [CoordinationReadiness.PARTIAL, CoordinationReadiness.BLOCKED],
    )
    def test_unready_requires_a_blocker(self, readiness: CoordinationReadiness) -> None:
        with pytest.raises(ValidationError):
            make_entry(readiness=readiness, blockers=())


class TestCoordinationView:
    """Verify the view is ordered, unique, and auditable."""

    def test_rejects_unordered_or_repeated_entries(self) -> None:
        with pytest.raises(ValidationError):
            make_view(
                entries=(
                    make_entry(course_code="NEURO"),
                    make_entry(course_code="GASTRO"),
                )
            )

        with pytest.raises(ValidationError):
            make_view(entries=(make_entry(), make_entry()))

    def test_rejects_naive_generation_timestamps(self) -> None:
        with pytest.raises(ValidationError):
            make_view(generated_at=datetime(2026, 8, 30, 12, 30))

    def test_requires_accountable_provenance(self) -> None:
        with pytest.raises(ValidationError):
            make_view(requested_by="  ")

        with pytest.raises(ValidationError):
            make_view(requested_by=2026)

    def test_exposes_readiness_projections(self) -> None:
        blocked = make_entry(
            course_code="GASTRO",
            readiness=CoordinationReadiness.BLOCKED,
            academic=make_summary(
                total_topics=0,
                completed_topics=0,
                in_progress_topics=0,
                not_started_topics=0,
                skipped_topics=0,
                next_required_topic_id=None,
            ),
            blockers=("syllabus: no planned topics are tracked for this course.",),
        )
        view = make_view(entries=(blocked, make_entry()))

        assert [entry.course_code for entry in view.blocked_courses] == ["GASTRO"]
        assert [entry.course_code for entry in view.fully_coordinated_courses] == ["NEURO"]
