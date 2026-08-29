"""Read-only Teaching Coach preview workflow with automatic topic selection."""

from medsemiotics.domain.exceptions import (
    TeachingCoachNoClassError,
    TeachingCoachScopeError,
    TeachingCoachTopicError,
)
from medsemiotics.domain.teaching_coach import (
    CuratedTeachingCoachDraftRequest,
    TeachingCoachPreviewRequest,
    TeachingCoachPreviewResult,
)
from medsemiotics.domain.teaching_position import TeachingPaceStatus, TeachingPosition
from medsemiotics.services.coaching_formatter import (
    build_teaching_event_title,
    format_coaching_brief,
)
from medsemiotics.services.curated_teaching_coach import CuratedTeachingCoachService
from medsemiotics.services.effective_teaching_day_service import EffectiveTeachingDayService


class TeachingCoachPreviewService:
    """Resolve the effective topic and return one formatted draft without ACT access."""

    def __init__(
        self,
        teaching_day_service: EffectiveTeachingDayService,
        curated_teaching_coach_service: CuratedTeachingCoachService,
    ) -> None:
        """Initialize with read-only schedule and curated drafting collaborators."""
        self._teaching_day_service = teaching_day_service
        self._curated_teaching_coach_service = curated_teaching_coach_service

    def preview_class_brief(
        self,
        request: TeachingCoachPreviewRequest,
    ) -> TeachingCoachPreviewResult:
        """Select the current topic and render a reviewable draft without publishing it."""
        position = self._teaching_day_service.get_position(
            semester_id=request.semester_id,
            course_code=request.course_code,
            target_date=request.class_date,
            time_min=request.time_min,
            time_max=request.time_max,
        )
        topic_id = self._resolve_topic(request, position)

        draft = self._curated_teaching_coach_service.draft_class_brief(
            CuratedTeachingCoachDraftRequest(
                semester_id=request.semester_id,
                course_code=request.course_code,
                class_date=request.class_date,
                time_min=request.time_min,
                time_max=request.time_max,
                topic_id=topic_id,
                requested_by=request.requested_by,
            )
        )
        return TeachingCoachPreviewResult(
            draft=draft,
            preview_title=build_teaching_event_title(
                course_code=draft.brief.course_code,
                topic_title=draft.brief.topic_title,
            ),
            preview_body=format_coaching_brief(draft.brief),
        )

    @staticmethod
    def _resolve_topic(
        request: TeachingCoachPreviewRequest,
        position: TeachingPosition,
    ) -> str:
        """Fail closed unless the effective position supplies one in-scope active topic."""
        if (
            position.semester_id != request.semester_id
            or position.course_code != request.course_code
            or position.target_date != request.class_date
        ):
            msg = "Teaching position scope does not match the Teaching Coach preview request."
            raise TeachingCoachScopeError(msg)
        if not position.is_class_date or position.pace_status == TeachingPaceStatus.UNAVAILABLE:
            msg = (
                f"No active effective class is available for {request.course_code} "
                f"on {request.class_date}."
            )
            raise TeachingCoachNoClassError(msg)
        if position.current_topic_id is None:
            msg = (
                f"No current topic needing coverage is available for {request.course_code} "
                f"on {request.class_date}."
            )
            raise TeachingCoachTopicError(msg)
        return position.current_topic_id
