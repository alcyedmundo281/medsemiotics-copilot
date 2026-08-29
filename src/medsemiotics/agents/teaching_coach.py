"""Deterministic Teaching Coach agent for safe, reviewable class briefing drafts."""

from medsemiotics.agents.framework import AgentCapabilityFramework
from medsemiotics.domain.academic_state import (
    CourseAcademicState,
    TopicProgressStatus,
)
from medsemiotics.domain.agents import AgentActionIntent, AgentPillar, AutonomyLevel
from medsemiotics.domain.coaching import CoachingBrief
from medsemiotics.domain.exceptions import (
    TeachingCoachNoClassError,
    TeachingCoachScopeError,
    TeachingCoachTopicError,
)
from medsemiotics.domain.teaching_coach import (
    TeachingCoachDraftRequest,
    TeachingCoachDraftResult,
)
from medsemiotics.domain.teaching_position import TeachingPaceStatus, TeachingPosition
from medsemiotics.services.course_state_service import CourseStateService
from medsemiotics.services.effective_teaching_day_service import EffectiveTeachingDayService

CAPABILITY_ID = "coaching.class-brief"

PACE_NOTES: dict[TeachingPaceStatus, str] = {
    TeachingPaceStatus.AHEAD: (
        "El curso está adelantado: reservar tiempo para integración clínica y comprobación "
        "de comprensión."
    ),
    TeachingPaceStatus.ON_TRACK: (
        "El curso está al día: mantener la secuencia prevista y verificar comprensión "
        "antes de avanzar."
    ),
    TeachingPaceStatus.BEHIND: (
        "El curso está atrasado: priorizar objetivos esenciales y diferir contenido accesorio."
    ),
    TeachingPaceStatus.NOT_STARTED: (
        "Es la primera cobertura del curso: activar conocimientos previos y explicitar el mapa "
        "de la sesión."
    ),
}

TOPIC_STATUS_NOTES: dict[TopicProgressStatus, str] = {
    TopicProgressStatus.NOT_STARTED: (
        "El tema aún no se ha enseñado: comenzar con conocimientos previos y objetivos."
    ),
    TopicProgressStatus.IN_PROGRESS: (
        "El tema está en progreso: recuperar lo ya cubierto antes de introducir contenido nuevo."
    ),
    TopicProgressStatus.COMPLETED: (
        "El tema figura como completado: tratar esta sesión como integración o repaso explícito."
    ),
    TopicProgressStatus.SKIPPED: (
        "El tema figura como omitido: confirmar su reincorporación antes de enseñarlo."
    ),
}


class TeachingCoachAgent:
    """Compose a CoachingBrief from curated guidance and authoritative read-only state."""

    def __init__(
        self,
        capability_framework: AgentCapabilityFramework,
        teaching_day_service: EffectiveTeachingDayService,
        course_state_service: CourseStateService,
    ) -> None:
        """Initialize the draft-only agent with read-only collaborators."""
        self._capability_framework = capability_framework
        self._teaching_day_service = teaching_day_service
        self._course_state_service = course_state_service

    def draft_class_brief(self, request: TeachingCoachDraftRequest) -> TeachingCoachDraftResult:
        """Draft one briefing without publishing or invoking any external write adapter."""
        decision = self._capability_framework.authorize(
            AgentActionIntent(
                agent=AgentPillar.COACHING,
                capability_id=CAPABILITY_ID,
                requested_autonomy=AutonomyLevel.DRAFT,
                requested_by=request.requested_by,
                rationale=(
                    f"Draft a class brief for {request.course_code} on {request.class_date}."
                ),
            )
        )

        position = self._teaching_day_service.get_position(
            semester_id=request.semester_id,
            course_code=request.course_code,
            target_date=request.class_date,
            time_min=request.time_min,
            time_max=request.time_max,
        )
        self._validate_position(request, position)

        state = self._course_state_service.get_state(
            semester_id=request.semester_id,
            course_code=request.course_code,
        )
        self._validate_state_scope(request, state)

        matching_topic = next(
            (topic for topic in state.topics if topic.topic_id == request.guide.topic_id),
            None,
        )
        if matching_topic is None:
            msg = (
                f"Topic '{request.guide.topic_id}' is not present in academic state for "
                f"{request.course_code} ({request.semester_id})."
            )
            raise TeachingCoachTopicError(msg)

        context_notes = self._build_context_notes(position, matching_topic.status)
        coaching_tips = [*request.guide.critical_points, *context_notes]

        brief = CoachingBrief(
            semester_id=request.semester_id,
            course_code=request.course_code,
            class_date=request.class_date,
            topic_id=request.guide.topic_id,
            topic_title=request.guide.topic_title,
            learning_objectives=request.guide.learning_objectives,
            coaching_tips=coaching_tips,
            teaching_questions=request.guide.teaching_questions,
            common_pitfalls=request.guide.common_pitfalls,
            material_notes=request.guide.material_notes,
            assignment_note=request.guide.assignment_note,
            powersemiotics_url=request.guide.powersemiotics_url,
        )

        return TeachingCoachDraftResult(
            brief=brief,
            teaching_position=position,
            topic_status=matching_topic.status,
            context_notes=context_notes,
            capability_decision=decision,
        )

    @staticmethod
    def _validate_position(
        request: TeachingCoachDraftRequest,
        position: TeachingPosition,
    ) -> None:
        """Reject cross-scope, inactive-date, or wrong-topic drafts."""
        if (
            position.semester_id != request.semester_id
            or position.course_code != request.course_code
            or position.target_date != request.class_date
        ):
            msg = "Teaching position scope does not match the Teaching Coach request."
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

        if position.current_topic_id != request.guide.topic_id:
            msg = (
                f"Guide topic '{request.guide.topic_id}' does not match current topic "
                f"'{position.current_topic_id}'."
            )
            raise TeachingCoachTopicError(msg)

    @staticmethod
    def _validate_state_scope(
        request: TeachingCoachDraftRequest,
        state: CourseAcademicState,
    ) -> None:
        """Reject academic state returned for another semester or course."""
        if state.semester_id != request.semester_id or state.course_code != request.course_code:
            msg = "Course academic state scope does not match the Teaching Coach request."
            raise TeachingCoachScopeError(msg)

    @staticmethod
    def _build_context_notes(
        position: TeachingPosition,
        topic_status: TopicProgressStatus,
    ) -> list[str]:
        """Build transparent deterministic advice from pace and topic status."""
        notes = [TOPIC_STATUS_NOTES[topic_status]]
        pace_note = PACE_NOTES.get(position.pace_status)
        if pace_note is not None:
            notes.append(pace_note)
        return notes
