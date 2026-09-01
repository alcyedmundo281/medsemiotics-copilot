"""Tests for catalog-backed, reviewable Classroom draft planning."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from medsemiotics.domain.assignment_catalog import CatalogAssignmentDraftRequest
from medsemiotics.domain.coordination_view import (
    AcademicProgressSummary,
    CalendarLink,
    CalendarLinkStatus,
    ClassroomLink,
    ClassroomLinkStatus,
    CoordinationReadiness,
    CourseCoordinationEntry,
)
from medsemiotics.domain.exceptions import CatalogClassroomDraftError
from medsemiotics.domain.external_courses import ExternalCourseLifecycle
from medsemiotics.services.assignment_catalog_repository import AssignmentCatalogRepository
from medsemiotics.services.catalog_classroom_assignment import (
    CatalogClassroomAssignmentService,
)
from medsemiotics.services.classroom_action_plan import ClassroomActionPlanner
from medsemiotics.services.syllabus_repository import SyllabusRepository
from tests.test_assignment_catalog_repository import VALID_CATALOG, write_catalog

PREPARED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def write_syllabus(root: Path, *, topic_id: str = "cranial-nerves") -> None:
    semester_dir = root / "2026-2"
    semester_dir.mkdir(parents=True)
    (semester_dir / "NEURO.yaml").write_text(
        (
            'semester_id: "2026-2"\n'
            'course_code: "NEURO"\n'
            "topics:\n"
            f'  - topic_id: "{topic_id}"\n'
            "    planned_order: 1\n"
            "    required: true\n"
        ),
        encoding="utf-8",
    )


def make_entry(*, course_code: str = "NEURO") -> CourseCoordinationEntry:
    return CourseCoordinationEntry(
        course_code=course_code,
        course_name="Semiología Neurológica",
        classroom=ClassroomLink(
            status=ClassroomLinkStatus.LINKED,
            external_id="770001",
            display_name="Semiología Neurológica 2026-2",
            lifecycle=ExternalCourseLifecycle.ACTIVE,
            reason="Exactly one course matched.",
        ),
        calendar=CalendarLink(
            status=CalendarLinkStatus.CONFIGURED,
            calendar_id="neuro@group.calendar.google.com",
            reason="Calendar is configured.",
        ),
        academic=AcademicProgressSummary(
            total_topics=1,
            completed_topics=0,
            in_progress_topics=0,
            not_started_topics=1,
            skipped_topics=0,
            next_required_topic_id="cranial-nerves",
        ),
        readiness=CoordinationReadiness.READY,
    )


def make_service(tmp_path: Path, *, syllabus_topic: str = "cranial-nerves") -> object:
    assignment_root = tmp_path / "assignments"
    syllabus_root = tmp_path / "syllabi"
    write_catalog(assignment_root, VALID_CATALOG)
    write_syllabus(syllabus_root, topic_id=syllabus_topic)
    return CatalogClassroomAssignmentService(
        assignment_repository=AssignmentCatalogRepository(assignment_root),
        syllabus_repository=SyllabusRepository(syllabus_root),
        action_planner=ClassroomActionPlanner(clock=lambda: PREPARED_AT),
    )


def make_request(**updates: object) -> CatalogAssignmentDraftRequest:
    values: dict[str, object] = {
        "semester_id": "2026-2",
        "course_code": "NEURO",
        "assignment_id": "cranial-case",
        "due_date": date(2026, 9, 10),
        "prepared_by": "course-director",
    }
    values.update(updates)
    return CatalogAssignmentDraftRequest(**values)  # type: ignore[arg-type]


class TestCatalogClassroomAssignmentService:
    def test_prepares_one_reviewable_draft_plan(self, tmp_path: Path) -> None:
        service = make_service(tmp_path)
        draft = service.prepare_draft(request=make_request(), entry=make_entry())  # type: ignore[attr-defined]

        assert draft.assignment.assignment_id == "cranial-case"
        assert draft.rubric.rubric_id == "neuro-rubric"
        assert draft.plan.external_course_id == "770001"
        assert draft.plan.topic_id == "cranial-nerves"
        assert draft.plan.due_date == date(2026, 9, 10)
        assert draft.plan.prepared_at == PREPARED_AT

    def test_renders_deliverable_rubric_and_privacy_review(self, tmp_path: Path) -> None:
        service = make_service(tmp_path)
        draft = service.prepare_draft(request=make_request(), entry=make_entry())  # type: ignore[attr-defined]
        instructions = draft.plan.instructions or ""

        assert "Productos esperados:" in instructions
        assert "Rúbrica cualitativa para revisión docente" in instructions
        assert "Reasoning (100%)" in instructions
        assert "casos sintéticos o desidentificados" in instructions
        assert "student_score" not in instructions

    def test_does_not_authorize_or_execute_the_plan(self, tmp_path: Path) -> None:
        service = make_service(tmp_path)
        draft = service.prepare_draft(request=make_request(), entry=make_entry())  # type: ignore[attr-defined]
        assert not hasattr(draft, "approval")
        assert not hasattr(service, "publish")
        assert not hasattr(service, "execute")

    def test_rejects_mismatched_coordination_course(self, tmp_path: Path) -> None:
        service = make_service(tmp_path)
        with pytest.raises(CatalogClassroomDraftError, match="does not match"):
            service.prepare_draft(  # type: ignore[attr-defined]
                request=make_request(),
                entry=make_entry(course_code="GASTRO"),
            )

    def test_rejects_assignment_topic_absent_from_syllabus(self, tmp_path: Path) -> None:
        service = make_service(tmp_path, syllabus_topic="motor-system")
        with pytest.raises(CatalogClassroomDraftError, match="absent from the tracked syllabus"):
            service.prepare_draft(request=make_request(), entry=make_entry())  # type: ignore[attr-defined]


def test_real_catalog_only_targets_topics_the_course_still_teaches() -> None:
    """Every tracked assignment must point at a topic of the official syllabus in force."""
    assignment_repository = AssignmentCatalogRepository(Path("config/assignments"))
    syllabus_repository = SyllabusRepository(Path("config/syllabi"))

    catalog = assignment_repository.get_catalog("2026-2", "NEURO")
    syllabus = syllabus_repository.get("2026-2", "NEURO")
    syllabus_topics = {topic.topic_id for topic in syllabus.topics}

    assert catalog.enabled is True
    assert catalog.assignments
    assert len(catalog.rubrics) == 1
    assert {assignment.topic_id for assignment in catalog.assignments} <= syllabus_topics
    assert all(
        assignment.rubric_id in {rubric.rubric_id for rubric in catalog.rubrics}
        for assignment in catalog.assignments
    )
    assert all("sint" in assignment.prompt.lower() for assignment in catalog.assignments)


def test_real_gastro_catalog_is_disabled_pending_recuration() -> None:
    """GASTRO moved to a clinical syllabus its assignment catalog does not cover yet."""
    catalog = AssignmentCatalogRepository(Path("config/assignments")).get_catalog(
        "2026-2", "GASTRO"
    )

    assert catalog.enabled is False
    assert catalog.assignments == ()
    assert catalog.rubrics == ()
