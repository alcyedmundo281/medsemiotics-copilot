"""Read-only orchestration from a curated guide catalog to a Teaching Coach draft."""

from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.domain.teaching_coach import (
    CuratedTeachingCoachDraftRequest,
    TeachingCoachDraftRequest,
    TeachingCoachDraftResult,
)
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository


class CuratedTeachingCoachService:
    """Load one reviewed guide and delegate deterministic draft composition to the agent."""

    def __init__(
        self,
        teaching_guide_repository: TeachingGuideRepository,
        teaching_coach_agent: TeachingCoachAgent,
    ) -> None:
        """Initialize with read-only guide and reasoning collaborators."""
        self._teaching_guide_repository = teaching_guide_repository
        self._teaching_coach_agent = teaching_coach_agent

    def draft_class_brief(
        self,
        request: CuratedTeachingCoachDraftRequest,
    ) -> TeachingCoachDraftResult:
        """Draft from a faculty-curated guide without invoking an ACT-layer collaborator."""
        guide = self._teaching_guide_repository.get_guide(
            semester_id=request.semester_id,
            course_code=request.course_code,
            topic_id=request.topic_id,
        )
        agent_request = TeachingCoachDraftRequest(
            semester_id=request.semester_id,
            course_code=request.course_code,
            class_date=request.class_date,
            time_min=request.time_min,
            time_max=request.time_max,
            guide=guide,
            requested_by=request.requested_by,
        )
        return self._teaching_coach_agent.draft_class_brief(agent_request)
