"""Tests for the Loop 0.6B persistent Apps Script Classroom read boundary."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    ClassroomAccessDecision,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_discovery import ClassroomCourseState
from medsemiotics.integrations.google_classroom import (
    APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR,
    APPS_SCRIPT_URL_ENV_VAR,
    AppsScriptCourseDiscoveryClient,
    AppsScriptDeployment,
    GoogleClassroomBoundaryError,
    GoogleClassroomConfigurationError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
    load_apps_script_deployment,
)

WEB_APP_URL = "https://script.google.com/macros/s/AKfycb-deployment/exec"
FIXED_NOW = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


class FakeTransport:
    """Record read attempts without performing any network request."""

    def __init__(
        self,
        envelope: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.envelope = envelope
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def fetch(self, *, url: str, operation: str) -> Mapping[str, Any]:
        """Return the configured envelope or raise the configured transport failure."""
        self.calls.append((url, operation))
        if self.error is not None:
            raise self.error
        assert self.envelope is not None
        return self.envelope


def make_envelope(**updates: object) -> dict[str, Any]:
    """Build the only reply envelope permitted by Loop 0.6B."""
    envelope: dict[str, Any] = {
        "operation": "course_discovery",
        "scopes": [GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE],
        "external_mutation": False,
        "courses": [
            {
                "id": "770002",
                "name": "Semiología Neurológica",
                "section": "NEURO-A",
                "course_state": "ACTIVE",
                "alternate_link": "https://classroom.google.com/c/770002",
            },
            {
                "id": "770001",
                "name": "Gastroenterología Clínica",
                "section": None,
                "course_state": "ARCHIVED",
                "alternate_link": None,
            },
        ],
    }
    envelope.update(updates)
    return envelope


def make_decision(**updates: object) -> ClassroomAccessDecision:
    """Build an allowed Loop 0.6A decision, or a deliberately broader forgery."""
    values: dict[str, object] = {
        "allowed": True,
        "operation": ClassroomOperation.COURSE_DISCOVERY,
        "approved_data_categories": (ClassroomDataCategory.COURSE_METADATA,),
        "approved_oauth_scopes": (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,),
        "reason": "Minimal read-only course discovery is permitted.",
    }
    values.update(updates)
    return ClassroomAccessDecision(**values)  # type: ignore[arg-type]


def make_client(transport: FakeTransport) -> AppsScriptCourseDiscoveryClient:
    """Build the read boundary with a deterministic clock."""
    return AppsScriptCourseDiscoveryClient(
        deployment=AppsScriptDeployment(
            deployment_id="AKfycb-deployment",
            web_app_url=WEB_APP_URL,
        ),
        transport=transport,
        clock=lambda: FIXED_NOW,
    )


class TestAppsScriptDeployment:
    """Verify the deployment descriptor cannot point anywhere but Apps Script."""

    def test_accepts_an_https_apps_script_url(self) -> None:
        deployment = AppsScriptDeployment(
            deployment_id="  AKfycb-deployment  ",
            web_app_url=f"  {WEB_APP_URL}  ",
        )

        assert deployment.deployment_id == "AKfycb-deployment"
        assert deployment.web_app_url == WEB_APP_URL

    @pytest.mark.parametrize(
        "rejected_url",
        [
            "http://script.google.com/macros/s/AKfycb/exec",
            "https://example.com/macros/s/AKfycb/exec",
            "https://script.google.com.attacker.test/macros/s/AKfycb/exec",
            "  ",
        ],
    )
    def test_rejects_non_apps_script_endpoints(self, rejected_url: str) -> None:
        with pytest.raises(ValidationError):
            AppsScriptDeployment(deployment_id="AKfycb", web_app_url=rejected_url)

    def test_rejects_a_missing_deployment_identifier(self) -> None:
        with pytest.raises(ValidationError):
            AppsScriptDeployment(deployment_id=770001, web_app_url=WEB_APP_URL)


class TestDeploymentConfiguration:
    """Verify configuration stays outside Git and fails closed when absent."""

    def test_loads_deployment_from_environment(self) -> None:
        deployment = load_apps_script_deployment(
            {
                APPS_SCRIPT_URL_ENV_VAR: WEB_APP_URL,
                APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR: "AKfycb-deployment",
            }
        )

        assert deployment.web_app_url == WEB_APP_URL

    def test_reports_missing_configuration_without_leaking_values(self) -> None:
        with pytest.raises(GoogleClassroomConfigurationError) as err:
            load_apps_script_deployment({APPS_SCRIPT_URL_ENV_VAR: WEB_APP_URL})

        assert APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR in str(err.value)
        assert WEB_APP_URL not in str(err.value)

    def test_rejects_invalid_configured_endpoint(self) -> None:
        with pytest.raises(GoogleClassroomConfigurationError):
            load_apps_script_deployment(
                {
                    APPS_SCRIPT_URL_ENV_VAR: "https://example.com/exec",
                    APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR: "AKfycb-deployment",
                }
            )


class TestCourseDiscoveryAuthorization:
    """Verify the boundary fails closed before contacting the deployment."""

    def test_denied_decision_blocks_the_read(self) -> None:
        transport = FakeTransport(make_envelope())

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(
                    allowed=False,
                    approved_data_categories=(),
                    approved_oauth_scopes=(),
                    reason="Course discovery is read-only and cannot mutate Classroom.",
                ),
                requested_by="course-director",
            )

        assert transport.calls == []

    def test_broader_approved_scope_blocks_the_read(self) -> None:
        transport = FakeTransport(make_envelope())

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(
                    approved_oauth_scopes=(
                        GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
                        "https://www.googleapis.com/auth/classroom.rosters.readonly",
                    )
                ),
                requested_by="course-director",
            )

        assert transport.calls == []

    def test_broader_approved_category_blocks_the_read(self) -> None:
        transport = FakeTransport(make_envelope())

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(
                    approved_data_categories=(
                        ClassroomDataCategory.COURSE_METADATA,
                        ClassroomDataCategory.ROSTERS,
                    )
                ),
                requested_by="course-director",
            )

        assert transport.calls == []


class TestCourseDiscoveryRead:
    """Verify sanitized metadata mapping and deterministic audit evidence."""

    def test_maps_sanitized_metadata_in_deterministic_order(self) -> None:
        transport = FakeTransport(make_envelope())

        discovery = make_client(transport).discover_courses(
            decision=make_decision(),
            requested_by="course-director",
        )

        assert transport.calls == [(WEB_APP_URL, "course_discovery")]
        assert [course.course_id for course in discovery.courses] == ["770001", "770002"]
        assert discovery.courses[0].course_state is ClassroomCourseState.ARCHIVED
        assert discovery.courses[0].section is None
        assert discovery.courses[1].alternate_link == "https://classroom.google.com/c/770002"
        assert discovery.requested_by == "course-director"
        assert discovery.retrieved_at == FIXED_NOW
        assert discovery.source_deployment_id == "AKfycb-deployment"
        assert discovery.approved_oauth_scopes == (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)

    def test_accepts_an_account_without_accessible_courses(self) -> None:
        transport = FakeTransport(make_envelope(courses=[]))

        discovery = make_client(transport).discover_courses(
            decision=make_decision(),
            requested_by="course-director",
        )

        assert discovery.courses == ()

    def test_wraps_transport_failures(self) -> None:
        transport = FakeTransport(error=TimeoutError("deployment unreachable"))

        with pytest.raises(GoogleClassroomReadError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_a_naive_clock(self) -> None:
        client = AppsScriptCourseDiscoveryClient(
            deployment=AppsScriptDeployment(
                deployment_id="AKfycb-deployment",
                web_app_url=WEB_APP_URL,
            ),
            transport=FakeTransport(make_envelope()),
            clock=lambda: datetime(2026, 8, 30, 12, 30),
        )

        with pytest.raises(GoogleClassroomMappingError):
            client.discover_courses(decision=make_decision(), requested_by="course-director")


class TestPayloadBoundary:
    """Verify student-level, mutating, or unrecognized payloads fail closed."""

    @pytest.mark.parametrize(
        "prohibited_field",
        [
            "students",
            "teachers",
            "roster",
            "enrollmentCode",
            "ownerId",
            "teacherGroupEmail",
            "courseWork",
            "submissions",
            "grades",
            "teacherFolder",
        ],
    )
    def test_rejects_prohibited_course_fields(self, prohibited_field: str) -> None:
        envelope = make_envelope()
        envelope["courses"][0][prohibited_field] = "leaked"
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomBoundaryError) as err:
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

        assert prohibited_field in str(err.value)

    def test_rejects_prohibited_envelope_fields(self) -> None:
        transport = FakeTransport(make_envelope(students=["student-1"]))

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_unrecognized_course_fields(self) -> None:
        envelope = make_envelope()
        envelope["courses"][0]["descriptionHeading"] = "extra"
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_a_declared_mutation(self) -> None:
        transport = FakeTransport(make_envelope(external_mutation=True))

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_a_broader_declared_scope(self) -> None:
        transport = FakeTransport(
            make_envelope(
                scopes=[
                    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
                    "https://www.googleapis.com/auth/classroom.rosters.readonly",
                ]
            )
        )

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_a_different_declared_operation(self) -> None:
        transport = FakeTransport(make_envelope(operation="roster_discovery"))

        with pytest.raises(GoogleClassroomBoundaryError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_an_incomplete_envelope(self) -> None:
        envelope = make_envelope()
        del envelope["scopes"]
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomReadError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    @pytest.mark.parametrize("malformed_courses", ["not-a-list", {"id": "770001"}])
    def test_rejects_malformed_course_collections(self, malformed_courses: object) -> None:
        transport = FakeTransport(make_envelope(courses=malformed_courses))

        with pytest.raises(GoogleClassroomReadError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_non_object_course_entries(self) -> None:
        transport = FakeTransport(make_envelope(courses=["770001"]))

        with pytest.raises(GoogleClassroomReadError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_non_text_course_values(self) -> None:
        envelope = make_envelope()
        envelope["courses"][0]["section"] = 12
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomMappingError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    @pytest.mark.parametrize("course_state", ["", "DELETED", None])
    def test_rejects_unusable_course_states(self, course_state: object) -> None:
        envelope = make_envelope()
        envelope["courses"][0]["course_state"] = course_state
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomMappingError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_duplicate_courses(self) -> None:
        envelope = make_envelope()
        envelope["courses"][1]["id"] = envelope["courses"][0]["id"]
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomMappingError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_a_non_object_reply(self) -> None:
        transport = FakeTransport([])  # type: ignore[arg-type]

        with pytest.raises(GoogleClassroomReadError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_non_string_field_names(self) -> None:
        envelope = make_envelope()
        envelope["courses"][0][1] = "leaked"
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomReadError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )

    def test_rejects_a_non_https_course_link(self) -> None:
        envelope = make_envelope()
        envelope["courses"][0]["alternate_link"] = "http://classroom.google.com/c/770002"
        transport = FakeTransport(envelope)

        with pytest.raises(GoogleClassroomMappingError):
            make_client(transport).discover_courses(
                decision=make_decision(),
                requested_by="course-director",
            )
