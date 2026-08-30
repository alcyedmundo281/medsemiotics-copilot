"""Tests for the Loop 0.6B Coordination course discovery service."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

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
from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.exceptions import AgentCapabilityConfigurationError
from medsemiotics.integrations.google_classroom import (
    AppsScriptCourseDiscoveryClient,
    AppsScriptDeployment,
)
from medsemiotics.services.classroom_course_discovery import (
    CAPABILITY_ID,
    ClassroomCourseDiscoveryService,
)

WEB_APP_URL = "https://script.google.com/macros/s/AKfycb-deployment/exec"
FIXED_NOW = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


class FakeTransport:
    """Return one sanitized envelope without any network request."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def fetch(self, *, url: str, operation: str) -> Mapping[str, Any]:
        """Record the read attempt and return sanitized course metadata."""
        self.calls.append((url, operation))
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


def make_service(
    transport: FakeTransport,
    framework: AgentCapabilityFramework | None = None,
) -> ClassroomCourseDiscoveryService:
    """Build the service over the deterministic read boundary."""
    client = AppsScriptCourseDiscoveryClient(
        deployment=AppsScriptDeployment(
            deployment_id="AKfycb-deployment",
            web_app_url=WEB_APP_URL,
        ),
        transport=transport,
        clock=lambda: FIXED_NOW,
    )
    return ClassroomCourseDiscoveryService(
        capability_framework=framework or build_default_agent_framework(),
        discovery_client=client,
    )


class TestClassroomCourseDiscoveryService:
    """Verify agent authorization and data-minimization precede every read."""

    def test_discovers_courses_under_observe_autonomy(self) -> None:
        transport = FakeTransport()

        discovery = make_service(transport).discover_courses(requested_by="course-director")

        assert transport.calls == [(WEB_APP_URL, "course_discovery")]
        assert [course.course_id for course in discovery.courses] == ["770001"]
        assert discovery.requested_by == "course-director"
        assert discovery.approved_oauth_scopes == (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)

    def test_declares_the_observe_only_coordination_capability(self) -> None:
        capability = build_default_agent_framework().get_capability(
            AgentPillar.COORDINATION,
            CAPABILITY_ID,
        )

        assert capability.maximum_autonomy is AutonomyLevel.OBSERVE
        assert capability.external_mutation is False

    def test_requires_a_registered_capability_before_reading(self) -> None:
        transport = FakeTransport()
        framework = AgentCapabilityFramework(
            profiles=[
                AgentProfile(
                    agent=AgentPillar.COORDINATION,
                    purpose="Align academic state without Classroom discovery.",
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
            make_service(transport, framework).discover_courses(requested_by="course-director")

        assert transport.calls == []

    def test_requests_only_metadata_and_the_readonly_scope(self) -> None:
        recorded: list[Any] = []

        class RecordingPolicy:
            """Capture the declaration the service submits to the access policy."""

            def authorize(self, request: Any) -> Any:
                recorded.append(request)
                from medsemiotics.services.classroom_access_policy import (
                    ClassroomAccessPolicy,
                )

                return ClassroomAccessPolicy().authorize(request)

        transport = FakeTransport()
        service = ClassroomCourseDiscoveryService(
            capability_framework=build_default_agent_framework(),
            discovery_client=AppsScriptCourseDiscoveryClient(
                deployment=AppsScriptDeployment(
                    deployment_id="AKfycb-deployment",
                    web_app_url=WEB_APP_URL,
                ),
                transport=transport,
                clock=lambda: FIXED_NOW,
            ),
            access_policy=RecordingPolicy(),  # type: ignore[arg-type]
        )

        service.discover_courses(requested_by="course-director")

        assert len(recorded) == 1
        request = recorded[0]
        assert request.operation is ClassroomOperation.COURSE_DISCOVERY
        assert request.data_categories == (ClassroomDataCategory.COURSE_METADATA,)
        assert request.oauth_scopes == (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)
        assert request.external_mutation is False
        assert request.requested_by == "course-director"
