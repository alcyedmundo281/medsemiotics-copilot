"""Tests for the Loop 0.6B sanitized Classroom course discovery domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
)
from medsemiotics.domain.classroom_discovery import (
    ClassroomCourseDiscovery,
    ClassroomCourseState,
    DiscoveredClassroomCourse,
)


def make_course(**updates: object) -> DiscoveredClassroomCourse:
    """Build one sanitized course metadata entry."""
    values: dict[str, object] = {
        "course_id": "770001",
        "name": "Semiología Neurológica",
        "section": "NEURO-A",
        "course_state": ClassroomCourseState.ACTIVE,
        "alternate_link": "https://classroom.google.com/c/770001",
    }
    values.update(updates)
    return DiscoveredClassroomCourse(**values)  # type: ignore[arg-type]


def make_discovery(**updates: object) -> ClassroomCourseDiscovery:
    """Build one discovery result with deterministic provenance."""
    values: dict[str, object] = {
        "requested_by": "course-director",
        "retrieved_at": datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        "source_deployment_id": "AKfycb-deployment",
        "approved_oauth_scopes": [GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE],
        "courses": [make_course()],
    }
    values.update(updates)
    return ClassroomCourseDiscovery(**values)  # type: ignore[arg-type]


class TestDiscoveredClassroomCourse:
    """Verify course metadata stays minimal, normalized, and immutable."""

    def test_normalizes_text_and_keeps_optional_metadata(self) -> None:
        course = make_course(course_id="  770001  ", name="  NEURO  ", section="   ")

        assert course.course_id == "770001"
        assert course.name == "NEURO"
        assert course.section is None

    def test_is_frozen_and_rejects_undeclared_fields(self) -> None:
        course = make_course()

        with pytest.raises(ValidationError):
            course.name = "changed"  # type: ignore[misc]

        with pytest.raises(ValidationError):
            DiscoveredClassroomCourse(  # type: ignore[call-arg]
                course_id="770001",
                name="NEURO",
                course_state=ClassroomCourseState.ACTIVE,
                students=["student-1"],
            )

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_rejects_blank_identity(self, blank: str) -> None:
        with pytest.raises(ValidationError):
            make_course(course_id=blank)

    def test_accepts_explicitly_absent_optional_metadata(self) -> None:
        course = make_course(section=None, alternate_link=None)

        assert course.section is None
        assert course.alternate_link is None

    def test_rejects_non_text_metadata(self) -> None:
        with pytest.raises(ValidationError):
            make_course(course_id=770001)

        with pytest.raises(ValidationError):
            make_course(section=12)

    def test_rejects_non_https_alternate_link(self) -> None:
        with pytest.raises(ValidationError):
            make_course(alternate_link="http://classroom.google.com/c/770001")

    def test_rejects_unsupported_course_state(self) -> None:
        with pytest.raises(ValidationError):
            make_course(course_state="deleted")


class TestClassroomCourseDiscovery:
    """Verify the discovery result is auditable, ordered, and rebuildable."""

    def test_orders_courses_deterministically(self) -> None:
        discovery = make_discovery(
            courses=[
                make_course(course_id="2", name="Gastroenterología"),
                make_course(course_id="1", name="semiología neurológica"),
                make_course(course_id="3", name="Ateneo clínico"),
            ]
        )

        assert [course.course_id for course in discovery.courses] == ["3", "2", "1"]

    def test_accepts_an_empty_course_list(self) -> None:
        assert make_discovery(courses=[]).courses == ()

    def test_rejects_duplicate_course_identifiers(self) -> None:
        with pytest.raises(ValidationError):
            make_discovery(
                courses=[
                    make_course(course_id="770001", name="NEURO"),
                    make_course(course_id="770001", name="GASTRO"),
                ]
            )

    def test_rejects_naive_timestamps(self) -> None:
        with pytest.raises(ValidationError):
            make_discovery(retrieved_at=datetime(2026, 8, 30, 12, 0))

    def test_rejects_missing_or_duplicated_scopes(self) -> None:
        with pytest.raises(ValidationError):
            make_discovery(approved_oauth_scopes=[])

        with pytest.raises(ValidationError):
            make_discovery(
                approved_oauth_scopes=[
                    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
                    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
                ]
            )

    def test_requires_accountable_provenance(self) -> None:
        with pytest.raises(ValidationError):
            make_discovery(requested_by="  ")

        with pytest.raises(ValidationError):
            make_discovery(source_deployment_id="  ")

    def test_rejects_malformed_collections(self) -> None:
        with pytest.raises(ValidationError):
            make_discovery(approved_oauth_scopes=GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE)

        with pytest.raises(ValidationError):
            make_discovery(courses="not-a-list")

        with pytest.raises(ValidationError):
            make_discovery(courses=["770001"])

    def test_accepts_course_metadata_supplied_as_mappings(self) -> None:
        discovery = make_discovery(
            courses=[
                {
                    "course_id": "770003",
                    "name": "Ateneo clínico",
                    "course_state": "active",
                }
            ]
        )

        assert discovery.courses[0].course_state is ClassroomCourseState.ACTIVE
        assert discovery.courses[0].alternate_link is None
