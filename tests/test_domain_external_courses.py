"""Tests for the Loop 0.6C provider-neutral private snapshot models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from medsemiotics.domain.external_courses import (
    ExternalCourse,
    ExternalCourseLifecycle,
    ExternalCourseProvider,
    ExternalCourseSnapshot,
    normalize_course_name,
)

SCOPE = "https://www.googleapis.com/auth/classroom.courses.readonly"
CAPTURED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def make_course(**updates: object) -> ExternalCourse:
    """Build one provider-neutral course."""
    values: dict[str, object] = {
        "provider": ExternalCourseProvider.GOOGLE_CLASSROOM,
        "external_id": "770001",
        "display_name": "Semiología Neurológica",
        "section": "NEURO-A",
        "lifecycle": ExternalCourseLifecycle.ACTIVE,
        "link": "https://classroom.google.com/c/770001",
    }
    values.update(updates)
    return ExternalCourse(**values)  # type: ignore[arg-type]


def make_snapshot(**updates: object) -> ExternalCourseSnapshot:
    """Build one private snapshot with deterministic provenance."""
    values: dict[str, object] = {
        "provider": ExternalCourseProvider.GOOGLE_CLASSROOM,
        "captured_at": CAPTURED_AT,
        "requested_by": "course-director",
        "source_reference": "AKfycb-deployment",
        "approved_scopes": [SCOPE],
        "courses": [make_course()],
    }
    values.update(updates)
    return ExternalCourseSnapshot(**values)  # type: ignore[arg-type]


class TestCourseNameNormalization:
    """Verify names fold deterministically before any later matching."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Semiología Neurológica", "semiologia neurologica"),
            ("  GASTRO   clínica  ", "gastro clinica"),
            ("NEURO\tII", "neuro ii"),
            ("Ateneo Clínico", "ateneo clinico"),
        ],
    )
    def test_folds_accents_case_and_whitespace(self, raw: str, expected: str) -> None:
        assert normalize_course_name(raw) == expected

    def test_exposes_the_normalized_name_on_the_course(self) -> None:
        course = make_course(display_name="  Semiología   NEUROLÓGICA ")

        assert course.display_name == "Semiología   NEUROLÓGICA"
        assert course.normalized_name == "semiologia neurologica"

    def test_rejects_a_name_without_comparable_characters(self) -> None:
        with pytest.raises(ValidationError):
            make_course(display_name="́́")


class TestExternalCourse:
    """Verify provider-neutral course metadata stays minimal and immutable."""

    def test_is_frozen_and_rejects_undeclared_fields(self) -> None:
        course = make_course()

        with pytest.raises(ValidationError):
            course.display_name = "changed"  # type: ignore[misc]

        with pytest.raises(ValidationError):
            ExternalCourse(  # type: ignore[call-arg]
                provider=ExternalCourseProvider.GOOGLE_CLASSROOM,
                external_id="770001",
                display_name="NEURO",
                lifecycle=ExternalCourseLifecycle.ACTIVE,
                students=["student-1"],
            )

    def test_normalizes_optional_metadata(self) -> None:
        course = make_course(section="   ", link=None)

        assert course.section is None
        assert course.link is None

    def test_rejects_a_non_https_link(self) -> None:
        with pytest.raises(ValidationError):
            make_course(link="http://classroom.google.com/c/770001")

    def test_rejects_blank_identity(self) -> None:
        with pytest.raises(ValidationError):
            make_course(external_id="  ")

    def test_rejects_non_text_metadata(self) -> None:
        with pytest.raises(ValidationError):
            make_course(external_id=770001)

        with pytest.raises(ValidationError):
            make_course(section=12)

    def test_rejects_an_unsupported_lifecycle(self) -> None:
        with pytest.raises(ValidationError):
            make_course(lifecycle="deleted")


class TestExternalCourseSnapshot:
    """Verify snapshot ordering, provenance, and privacy affordances."""

    def test_orders_courses_by_normalized_name(self) -> None:
        snapshot = make_snapshot(
            courses=[
                make_course(external_id="2", display_name="Semiología Neurológica"),
                make_course(external_id="1", display_name="ateneo clinico"),
                make_course(external_id="3", display_name="Gastroenterología"),
            ]
        )

        assert [course.external_id for course in snapshot.courses] == ["1", "3", "2"]

    def test_rejects_duplicate_provider_identifier_pairs(self) -> None:
        with pytest.raises(ValidationError):
            make_snapshot(
                courses=[
                    make_course(external_id="770001", display_name="NEURO"),
                    make_course(external_id="770001", display_name="GASTRO"),
                ]
            )

    def test_allows_two_courses_sharing_a_normalized_name(self) -> None:
        snapshot = make_snapshot(
            courses=[
                make_course(external_id="770001", display_name="Semiología"),
                make_course(external_id="770002", display_name="semiologia"),
            ]
        )

        assert len(snapshot.courses) == 2

    def test_rejects_naive_capture_timestamps(self) -> None:
        with pytest.raises(ValidationError):
            make_snapshot(captured_at=datetime(2026, 8, 30, 12, 30))

    def test_requires_accountable_provenance_and_scopes(self) -> None:
        with pytest.raises(ValidationError):
            make_snapshot(requested_by="  ")

        with pytest.raises(ValidationError):
            make_snapshot(source_reference="  ")

        with pytest.raises(ValidationError):
            make_snapshot(approved_scopes=[])

        with pytest.raises(ValidationError):
            make_snapshot(approved_scopes=[SCOPE, SCOPE])

        with pytest.raises(ValidationError):
            make_snapshot(approved_scopes=SCOPE)

    def test_rejects_malformed_course_collections(self) -> None:
        with pytest.raises(ValidationError):
            make_snapshot(courses="not-a-list")

        with pytest.raises(ValidationError):
            make_snapshot(courses=["770001"])

    def test_accepts_courses_supplied_as_mappings(self) -> None:
        snapshot = make_snapshot(
            courses=[
                {
                    "provider": ExternalCourseProvider.GOOGLE_CLASSROOM,
                    "external_id": "770003",
                    "display_name": "Ateneo",
                    "lifecycle": ExternalCourseLifecycle.ARCHIVED,
                }
            ]
        )

        assert snapshot.courses[0].link is None

    def test_accepts_a_provider_without_accessible_courses(self) -> None:
        snapshot = make_snapshot(courses=[])

        assert snapshot.courses == ()
        assert snapshot.audit_summary().course_count == 0
        assert snapshot.audit_summary().lifecycle_counts == ()


class TestSnapshotFingerprint:
    """Verify change detection works without retaining course content."""

    def test_is_stable_across_equivalent_snapshots(self) -> None:
        first = make_snapshot()
        second = make_snapshot(
            captured_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
            requested_by="department-head",
        )

        assert first.fingerprint == second.fingerprint
        assert first.has_same_content(second) is True

    def test_is_insensitive_to_display_only_differences(self) -> None:
        first = make_snapshot(courses=[make_course(display_name="Semiología Neurológica")])
        second = make_snapshot(courses=[make_course(display_name="  SEMIOLOGIA  neurologica ")])

        assert first.has_same_content(second) is True

    @pytest.mark.parametrize(
        "changed_course",
        [
            {"external_id": "770009"},
            {"display_name": "Otra materia"},
            {"section": "NEURO-B"},
            {"lifecycle": ExternalCourseLifecycle.ARCHIVED},
        ],
    )
    def test_changes_when_course_content_changes(self, changed_course: dict[str, object]) -> None:
        baseline = make_snapshot()
        changed = make_snapshot(courses=[make_course(**changed_course)])

        assert baseline.fingerprint != changed.fingerprint
        assert baseline.has_same_content(changed) is False

    def test_changes_when_a_course_appears(self) -> None:
        baseline = make_snapshot()
        extended = make_snapshot(
            courses=[make_course(), make_course(external_id="770002", display_name="GASTRO")]
        )

        assert baseline.has_same_content(extended) is False


class TestSnapshotAuditSummary:
    """Verify only redacted provenance may leave the process."""

    def test_reports_counts_and_provenance_without_course_content(self) -> None:
        snapshot = make_snapshot(
            courses=[
                make_course(external_id="1", display_name="NEURO"),
                make_course(external_id="2", display_name="GASTRO"),
                make_course(
                    external_id="3",
                    display_name="Ateneo",
                    lifecycle=ExternalCourseLifecycle.ARCHIVED,
                ),
            ]
        )

        summary = snapshot.audit_summary()
        rendered = summary.model_dump_json()

        assert summary.course_count == 3
        assert summary.lifecycle_counts == (
            (ExternalCourseLifecycle.ACTIVE, 2),
            (ExternalCourseLifecycle.ARCHIVED, 1),
        )
        assert summary.fingerprint == snapshot.fingerprint
        assert summary.source_reference == "AKfycb-deployment"
        for leaked in ("NEURO", "GASTRO", "Ateneo", "770001", "classroom.google.com", "NEURO-A"):
            assert leaked not in rendered

    def test_orders_lifecycle_counts_deterministically(self) -> None:
        snapshot = make_snapshot(
            courses=[
                make_course(external_id="1", lifecycle=ExternalCourseLifecycle.SUSPENDED),
                make_course(external_id="2", lifecycle=ExternalCourseLifecycle.ACTIVE),
                make_course(external_id="3", lifecycle=ExternalCourseLifecycle.PROVISIONED),
            ]
        )

        assert [lifecycle for lifecycle, _ in snapshot.audit_summary().lifecycle_counts] == [
            ExternalCourseLifecycle.ACTIVE,
            ExternalCourseLifecycle.PROVISIONED,
            ExternalCourseLifecycle.SUSPENDED,
        ]
