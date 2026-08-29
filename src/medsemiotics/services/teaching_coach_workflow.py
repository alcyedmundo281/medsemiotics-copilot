"""Application workflow separating Teaching Coach drafting from approved publication."""

from medsemiotics.agents.framework import AgentCapabilityFramework
from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.domain.agents import (
    AgentActionIntent,
    AgentAuthorizationContext,
    AgentPillar,
    AutonomyLevel,
)
from medsemiotics.domain.teaching_coach import (
    TeachingCoachDraftRequest,
    TeachingCoachDraftResult,
    TeachingCoachPublishRequest,
    TeachingCoachPublishResult,
)
from medsemiotics.services.calendar_coaching_service import CalendarCoachingService

PUBLISH_CAPABILITY_ID = "coaching.calendar-brief-publish"


class TeachingCoachWorkflow:
    """Coordinate draft and publish as two intentionally separate operations."""

    def __init__(
        self,
        teaching_coach_agent: TeachingCoachAgent,
        capability_framework: AgentCapabilityFramework,
        calendar_coaching_service: CalendarCoachingService,
    ) -> None:
        """Initialize the workflow with separate REASON, policy, and ACT collaborators."""
        self._teaching_coach_agent = teaching_coach_agent
        self._capability_framework = capability_framework
        self._calendar_coaching_service = calendar_coaching_service

    def draft(self, request: TeachingCoachDraftRequest) -> TeachingCoachDraftResult:
        """Produce a reviewable draft without invoking the ACT collaborator."""
        return self._teaching_coach_agent.draft_class_brief(request)

    def publish(
        self,
        request: TeachingCoachPublishRequest,
        authorization: AgentAuthorizationContext,
    ) -> TeachingCoachPublishResult:
        """Publish one reviewed draft only after an explicit level-3 policy decision."""
        decision = self._capability_framework.authorize(
            AgentActionIntent(
                agent=AgentPillar.COACHING,
                capability_id=PUBLISH_CAPABILITY_ID,
                requested_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                requested_by=request.requested_by,
                rationale=(
                    f"Publish reviewed Teaching Coach brief for "
                    f"{request.draft.brief.course_code} on {request.draft.brief.class_date}."
                ),
            ),
            authorization,
        )

        brief = request.draft.brief
        calendar_result = self._calendar_coaching_service.publish_class_brief(
            semester_id=brief.semester_id,
            course_code=brief.course_code,
            class_date=brief.class_date,
            brief=brief,
            time_min=request.time_min,
            time_max=request.time_max,
            reminders_minutes=request.reminders_minutes,
            authorized=True,
        )
        return TeachingCoachPublishResult(
            calendar_result=calendar_result,
            capability_decision=decision,
        )
