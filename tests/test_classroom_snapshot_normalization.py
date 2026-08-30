"""Tests for the Loop 0.6C Classroom snapshot normalization service."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
)
from medsemiotics.domain.classroom_discovery import (
    ClassroomCourseDiscovery,
    ClassroomCourseState,
)
from medsemiotics.domain.exceptions import ExternalCourseSnapshotError
from medsemiotics.domain.external_courses import (
    ExternalCourseLifecycle,
    ExternalCourseProvider,
)
from medsemiotics.integrations.google_classroom import (
    AppsScriptCourseDiscoveryClient,
    AppsScriptDeployment,
)
from medsemiotics.services.classroom_course_discovery import (
    ClassroomCourseDiscoveryService,
)
from medsemiotics.services.classroom_snapshot import (
    LIFECYCLE_BY_CLASSROOM_STATE,
    ClassroomSnapshotNormalizer,
)

WEB_APP_URL = "https://script.google.com/macros/s/AKfycb-deployment/exec"
RETRIEVED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def make_discovery(**updates: object) -> ClassroomCourseDiscovery:
    """Build one authorized, sanitized Classroom discovery result."""
    values: dict[str, object] = {
        "requested_by": "course-director",
        "retrieved_at": RETRIEVED_AT,
        "source_deployment_id": "AKfycb-deployment",
        "approved_oauth_scopes": [GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE],
        "courses": [
            {
                "course_id": "770002",
                "name": "Semiología Neurológica",
                "section": "NEURO-A",
                "course_state": ClassroomCourseState.ACTIVE,
                "alternate_link": "https://classroom.google.com/c/770002",
            },
            {
                "course_id": "770001",
                "name": "Ateneo Clínico",
                "course_state": ClassroomCourseState.ARCHIVED,
            },
        ],
    }
    values.update(updates)
    return ClassroomCourseDiscovery(**values)  # type: ignore[arg-type]


class TestClassroomSnapshotNormalizer:
    """Verify provider-neutral normalization preserves provenance and adds no authority."""

    def test_maps_courses_and_carries_provenance(self) -> None:
        snapshot = ClassroomSnapshotNormalizer().normalize(make_discovery())

        assert snapshot.provider is ExternalCourseProvider.GOOGLE_CLASSROOM
        assert snapshot.captured_at == RETRIEVED_AT
        assert snapshot.requested_by == "course-director"
        assert snapshot.source_reference == "AKfycb-deployment"
        assert snapshot.approved_scopes == (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)

        ateneo, neuro = snapshot.courses
        assert ateneo.external_id == "770001"
        assert ateneo.normalized_name == "ateneo clinico"
        assert ateneo.lifecycle is ExternalCourseLifecycle.ARCHIVED
        assert ateneo.section is None
        assert ateneo.link is None
        assert neuro.display_name == "Semiología Neurológica"
        assert neuro.normalized_name == "semiologia neurologica"
        assert neuro.section == "NEURO-A"
        assert neuro.link == "https://classroom.google.com/c/770002"

    @pytest.mark.parametrize("state", list(ClassroomCourseState))
    def test_maps_every_classroom_state(self, state: ClassroomCourseState) -> None:
        discovery = make_discovery(
            courses=[{"course_id": "770001", "name": "NEURO", "course_state": state}]
        )

        snapshot = ClassroomSnapshotNormalizer().normalize(discovery)

        assert snapshot.courses[0].lifecycle is LIFECYCLE_BY_CLASSROOM_STATE[state]
        assert snapshot.courses[0].lifecycle.value == state.value

    def test_normalizes_an_account_without_courses(self) -> None:
        snapshot = ClassroomSnapshotNormalizer().normalize(make_discovery(courses=[]))

        assert snapshot.courses == ()
        assert snapshot.audit_summary().course_count == 0

    def test_is_deterministic_for_the_same_discovery(self) -> None:
        normalizer = ClassroomSnapshotNormalizer()
        discovery = make_discovery()

        first = normalizer.normalize(discovery)
        second = normalizer.normalize(discovery)

        assert first == second
        assert first.fingerprint == second.fingerprint

    def test_detects_a_changed_course_between_reads(self) -> None:
        normalizer = ClassroomSnapshotNormalizer()
        baseline = normalizer.normalize(make_discovery())
        later = normalizer.normalize(
            make_discovery(
                retrieved_at=datetime(2026, 9, 6, 12, 30, tzinfo=UTC),
                courses=[
                    {
                        "course_id": "770002",
                        "name": "Semiología Neurológica",
                        "section": "NEURO-A",
                        "course_state": ClassroomCourseState.ARCHIVED,
                        "alternate_link": "https://classroom.google.com/c/770002",
                    },
                    {
                        "course_id": "770001",
                        "name": "Ateneo Clínico",
                        "course_state": ClassroomCourseState.ARCHIVED,
                    },
                ],
            )
        )

        assert baseline.has_same_content(later) is False

    def test_ignores_a_read_that_only_differs_in_capture_metadata(self) -> None:
        normalizer = ClassroomSnapshotNormalizer()
        baseline = normalizer.normalize(make_discovery())
        later = normalizer.normalize(
            make_discovery(
                retrieved_at=datetime(2026, 9, 6, 12, 30, tzinfo=UTC),
                requested_by="department-head",
            )
        )

        assert baseline.has_same_content(later) is True


class TestNormalizationFailsClosed:
    """Verify unmappable provider data never becomes a silently degraded snapshot."""

    def test_rejects_a_state_without_a_provider_neutral_equivalent(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delitem(LIFECYCLE_BY_CLASSROOM_STATE, ClassroomCourseState.SUSPENDED)
        discovery = make_discovery(
            courses=[
                {
                    "course_id": "770001",
                    "name": "NEURO",
                    "course_state": ClassroomCourseState.SUSPENDED,
                }
            ]
        )

        with pytest.raises(ExternalCourseSnapshotError) as err:
            ClassroomSnapshotNormalizer().normalize(discovery)

        assert "suspended" in str(err.value)

    def test_rejects_provider_data_that_cannot_form_a_valid_snapshot(self) -> None:
        duplicated = make_discovery()
        broken = duplicated.model_copy(
            update={
                "courses": (
                    duplicated.courses[0],
                    duplicated.courses[0].model_copy(update={"name": "Otro nombre"}),
                )
            }
        )

        with pytest.raises(ExternalCourseSnapshotError) as err:
            ClassroomSnapshotNormalizer().normalize(broken)

        assert "could not be normalized" in str(err.value)


class FakeTransport:
    """Return one sanitized envelope without any network request."""

    def fetch(self, *, url: str, operation: str) -> Mapping[str, Any]:  # noqa: ARG002
        """Return sanitized Classroom course metadata."""
        return {
            "operation": "course_discovery",
            "scopes": [GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE],
            "external_mutation": False,
            "courses": [
                {
                    "id": "770001",
                    "name": "Gastroenterología Clínica",
                    "section": "GASTRO-A",
                    "course_state": "ACTIVE",
                    "alternate_link": "https://classroom.google.com/c/770001",
                }
            ],
        }


class TestAuthorizedReadToSnapshot:
    """Verify the authorized read boundary and normalization compose end to end."""

    def test_produces_a_snapshot_from_an_authorized_read(self) -> None:
        service = ClassroomCourseDiscoveryService(
            capability_framework=build_default_agent_framework(),
            discovery_client=AppsScriptCourseDiscoveryClient(
                deployment=AppsScriptDeployment(
                    deployment_id="AKfycb-deployment",
                    web_app_url=WEB_APP_URL,
                ),
                transport=FakeTransport(),
                clock=lambda: RETRIEVED_AT,
            ),
        )

        snapshot = ClassroomSnapshotNormalizer().normalize(
            service.discover_courses(requested_by="course-director")
        )

        assert snapshot.provider is ExternalCourseProvider.GOOGLE_CLASSROOM
        assert [course.normalized_name for course in snapshot.courses] == [
            "gastroenterologia clinica"
        ]
        assert snapshot.approved_scopes == (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)
        assert snapshot.audit_summary().fingerprint == snapshot.fingerprint
