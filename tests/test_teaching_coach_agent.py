"""Tests for the deterministic, draft-only Teaching Coach agent."""

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.domain.academic_state import (
    CourseAcademicState,
    TopicProgress,
    TopicProgressStatus,
)
from medsemiotics.domain.exceptions import (
    TeachingCoachNoClassError,
    TeachingCoachScopeError,
    TeachingCoachTopicError,
)
from medsemiotics.domain.teaching_coach import (
    TeachingCoachDraftRequest,
    TeachingTopicGuide,
)
from medsemiotics.domain.teaching_position import (
    TeachingPaceStatus,
    TeachingPosition,
)
from medsemiotics.services.course_state_service import CourseStateService
from medsemiotics.services.effective_teaching_day_service import EffectiveTeachingDayService


@pytest.fixture
def topic_guide() -> TeachingTopicGuide:
    return TeachingTopicGuide(
        topic_id="coordination-cerebellum",
        topic_title="Coordinación y cerebelo",
        learning_objectives=["Distinguir ataxia cerebelosa de ataxia sensitiva."],
        critical_points=["Comparar marcha y respuesta en la prueba de Romberg."],
        teaching_questions=["¿Qué cambia al cerrar los ojos?"],
        common_pitfalls=["Interpretar todo Romberg positivo como lesión cerebelosa."],
        material_notes=["Espacio seguro para evaluar la marcha."],
        assignment_note="Revisar vías espinocerebelosas.",
        powersemiotics_url="https://powersemiotics.org/cerebelo",
    )


@pytest.fixture
def draft_request(topic_guide: TeachingTopicGuide) -> TeachingCoachDraftRequest:
    tz = ZoneInfo("America/Guayaquil")
    return TeachingCoachDraftRequest(
        semester_id="2026-2",
        course_code="NEURO",
        class_date=date(2026, 9, 1),
        time_min=datetime(2026, 9, 1, 0, 0, tzinfo=tz),
        time_max=datetime(2026, 9, 2, 0, 0, tzinfo=tz),
        guide=topic_guide,
        requested_by="course-director",
    )


@pytest.fixture
def teaching_position() -> TeachingPosition:
    return TeachingPosition(
        semester_id="2026-2",
        course_code="NEURO",
        target_date=date(2026, 9, 1),
        is_class_date=True,
        expected_session_count=5,
        actual_session_count=4,
        expected_topic_order=5,
        current_topic_id="coordination-cerebellum",
        pace_status=TeachingPaceStatus.BEHIND,
        topic_delta=-1,
    )


@pytest.fixture
def course_state() -> CourseAcademicState:
    return CourseAcademicState(
        semester_id="2026-2",
        course_code="NEURO",
        topics=[
            TopicProgress(
                topic_id="coordination-cerebellum",
                planned_order=5,
                required=True,
                status=TopicProgressStatus.NOT_STARTED,
            )
        ],
    )


@pytest.fixture
def collaborators(
    teaching_position: TeachingPosition,
    course_state: CourseAcademicState,
) -> tuple[MagicMock, MagicMock]:
    day_service = MagicMock(spec=EffectiveTeachingDayService)
    day_service.get_position.return_value = teaching_position
    state_service = MagicMock(spec=CourseStateService)
    state_service.get_state.return_value = course_state
    return day_service, state_service


def make_agent(day_service: MagicMock, state_service: MagicMock) -> TeachingCoachAgent:
    """Build the agent with the default 0.5A capability policy and read-only mocks."""
    return TeachingCoachAgent(
        capability_framework=build_default_agent_framework(),
        teaching_day_service=day_service,
        course_state_service=state_service,
    )


class TestTeachingCoachAgent:
    """Verify safe contextual composition of class briefing drafts."""

    def test_drafts_contextual_coaching_brief(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
    ) -> None:
        day_service, state_service = collaborators
        result = make_agent(day_service, state_service).draft_class_brief(draft_request)

        assert result.brief.topic_id == "coordination-cerebellum"
        assert result.brief.learning_objectives == draft_request.guide.learning_objectives
        assert result.brief.coaching_tips[0] == draft_request.guide.critical_points[0]
        assert any("aún no se ha enseñado" in note for note in result.context_notes)
        assert any("curso está atrasado" in note for note in result.context_notes)
        assert result.capability_decision.allowed is True
        assert result.capability_decision.requested_autonomy.name == "DRAFT"
        day_service.get_position.assert_called_once()
        state_service.get_state.assert_called_once_with(semester_id="2026-2", course_code="NEURO")

    def test_in_progress_topic_adds_retrieval_guidance(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
        course_state: CourseAcademicState,
    ) -> None:
        day_service, state_service = collaborators
        in_progress = course_state.model_copy(
            update={
                "topics": [
                    course_state.topics[0].model_copy(
                        update={
                            "status": TopicProgressStatus.IN_PROGRESS,
                            "first_taught_date": date(2026, 8, 25),
                            "last_taught_date": date(2026, 8, 25),
                            "session_count": 1,
                        }
                    )
                ]
            }
        )
        state_service.get_state.return_value = in_progress

        result = make_agent(day_service, state_service).draft_class_brief(draft_request)
        assert any("recuperar lo ya cubierto" in note for note in result.context_notes)

    def test_non_class_date_is_rejected_before_loading_course_state(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
        teaching_position: TeachingPosition,
    ) -> None:
        day_service, state_service = collaborators
        day_service.get_position.return_value = teaching_position.model_copy(
            update={"is_class_date": False}
        )

        with pytest.raises(TeachingCoachNoClassError, match="No active effective class"):
            make_agent(day_service, state_service).draft_class_brief(draft_request)
        state_service.get_state.assert_not_called()

    def test_wrong_guide_topic_is_rejected(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
    ) -> None:
        day_service, state_service = collaborators
        wrong_guide = draft_request.guide.model_copy(update={"topic_id": "cranial-nerves"})
        wrong_request = draft_request.model_copy(update={"guide": wrong_guide})

        with pytest.raises(TeachingCoachTopicError, match="does not match current topic"):
            make_agent(day_service, state_service).draft_class_brief(wrong_request)
        state_service.get_state.assert_not_called()

    def test_no_current_topic_is_rejected(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
        teaching_position: TeachingPosition,
    ) -> None:
        day_service, state_service = collaborators
        day_service.get_position.return_value = teaching_position.model_copy(
            update={"current_topic_id": None, "pace_status": TeachingPaceStatus.COMPLETE}
        )

        with pytest.raises(TeachingCoachTopicError, match="No current topic"):
            make_agent(day_service, state_service).draft_class_brief(draft_request)
        state_service.get_state.assert_not_called()

    def test_topic_missing_from_academic_state_is_rejected(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
        course_state: CourseAcademicState,
    ) -> None:
        day_service, state_service = collaborators
        state_service.get_state.return_value = course_state.model_copy(update={"topics": []})

        with pytest.raises(TeachingCoachTopicError, match="not present in academic state"):
            make_agent(day_service, state_service).draft_class_brief(draft_request)

    def test_mismatched_position_scope_is_rejected(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
        teaching_position: TeachingPosition,
    ) -> None:
        day_service, state_service = collaborators
        day_service.get_position.return_value = teaching_position.model_copy(
            update={"course_code": "GASTRO"}
        )

        with pytest.raises(TeachingCoachScopeError, match="position scope"):
            make_agent(day_service, state_service).draft_class_brief(draft_request)
        state_service.get_state.assert_not_called()

    def test_mismatched_academic_state_scope_is_rejected(
        self,
        draft_request: TeachingCoachDraftRequest,
        collaborators: tuple[MagicMock, MagicMock],
        course_state: CourseAcademicState,
    ) -> None:
        day_service, state_service = collaborators
        state_service.get_state.return_value = course_state.model_copy(
            update={"course_code": "GASTRO"}
        )

        with pytest.raises(TeachingCoachScopeError, match="academic state scope"):
            make_agent(day_service, state_service).draft_class_brief(draft_request)
