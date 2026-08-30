"""Coordination service for metadata-only Google Classroom course discovery."""

from medsemiotics.agents.framework import AgentCapabilityFramework
from medsemiotics.domain.agents import AgentActionIntent, AgentPillar, AutonomyLevel
from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    ClassroomAccessRequest,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_discovery import ClassroomCourseDiscovery
from medsemiotics.integrations.google_classroom.apps_script import (
    AppsScriptCourseDiscoveryClient,
)
from medsemiotics.services.classroom_access_policy import ClassroomAccessPolicy

CAPABILITY_ID = "coordination.classroom-course-discovery"


class ClassroomCourseDiscoveryService:
    """Authorize and execute one OBSERVE-only Classroom course discovery read."""

    def __init__(
        self,
        capability_framework: AgentCapabilityFramework,
        discovery_client: AppsScriptCourseDiscoveryClient,
        access_policy: ClassroomAccessPolicy | None = None,
    ) -> None:
        """Initialize with the four-C capability registry and the Apps Script read boundary."""
        self._capability_framework = capability_framework
        self._discovery_client = discovery_client
        self._access_policy = access_policy or ClassroomAccessPolicy()

    def discover_courses(self, *, requested_by: str) -> ClassroomCourseDiscovery:
        """Discover accessible courses after both agent and data-minimization authorization.

        Args:
            requested_by: Accountable requester recorded in every authorization decision.

        Returns:
            Sanitized, deterministically ordered ClassroomCourseDiscovery.

        Raises:
            AgentAuthorizationError: If the intent exceeds the Coordination OBSERVE boundary.
            ClassroomAccessPolicyError: If the declared data or OAuth authority exceeds policy.
            GoogleClassroomError: If the read boundary rejects or cannot obtain the payload.
        """
        self._capability_framework.authorize(
            AgentActionIntent(
                agent=AgentPillar.COORDINATION,
                capability_id=CAPABILITY_ID,
                requested_autonomy=AutonomyLevel.OBSERVE,
                requested_by=requested_by,
                rationale="Discover accessible Classroom courses using metadata only.",
            )
        )

        decision = self._access_policy.authorize(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSE_DISCOVERY,
                data_categories=(ClassroomDataCategory.COURSE_METADATA,),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,),
                requested_by=requested_by,
                external_mutation=False,
            )
        )

        return self._discovery_client.discover_courses(
            decision=decision,
            requested_by=requested_by,
        )
