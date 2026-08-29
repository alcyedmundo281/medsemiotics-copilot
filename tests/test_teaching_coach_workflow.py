"""Tests for the double-gated Teaching Coach publication workflow."""

from unittest.mock import MagicMock

import pytest

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.domain.agents import AgentAuthorizationContext, AutonomyLevel
from medsemiotics.domain.coaching import CalendarPublishAction, CalendarPublishResult
from medsemiotics.domain.exceptions import AgentAuthorizationError
from medsemiotics.domain.teaching_coach import (
    TeachingCoachDraftRequest,
    TeachingCoachDraftResult,
)
from medsemiotics.services.calendar_coaching_service import CalendarCoachingService
from medsemiotics.services.teaching_coach_workflow import TeachingCoachWorkflow
from tests.test_domain_teaching_coach_publish import make_publish_request


@pytest.fixture
def collaborators() -> tuple[MagicMock, MagicMock]:
    agent = MagicMock(spec=TeachingCoachAgent)
    calendar = MagicMock(spec=CalendarCoachingService)
    calendar.publish_class_brief.return_value = CalendarPublishResult(
        calendar_id="cal_neuro",
        event_id="event_123",
        action=CalendarPublishAction.CREATED,
    )
    return agent, calendar


def make_workflow(agent: MagicMock, calendar: MagicMock) -> TeachingCoachWorkflow:
    return TeachingCoachWorkflow(
        teaching_coach_agent=agent,
        capability_framework=build_default_agent_framework(),
        calendar_coaching_service=calendar,
    )


class TestTeachingCoachWorkflow:
    """Verify the review boundary and double authorization gate."""

    def test_draft_never_calls_calendar(
        self,
        collaborators: tuple[MagicMock, MagicMock],
    ) -> None:
        agent, calendar = collaborators
        request = MagicMock(spec=TeachingCoachDraftRequest)
        expected = MagicMock(spec=TeachingCoachDraftResult)
        agent.draft_class_brief.return_value = expected

        result = make_workflow(agent, calendar).draft(request)

        assert result is expected
        agent.draft_class_brief.assert_called_once_with(request)
        calendar.publish_class_brief.assert_not_called()

    def test_publish_without_approval_is_denied_before_calendar(
        self,
        collaborators: tuple[MagicMock, MagicMock],
    ) -> None:
        agent, calendar = collaborators
        request = make_publish_request()

        with pytest.raises(AgentAuthorizationError, match="requires explicit human approval"):
            make_workflow(agent, calendar).publish(
                request,
                AgentAuthorizationContext(),
            )
        calendar.publish_class_brief.assert_not_called()

    def test_trusted_flag_does_not_bypass_level_three_approval(
        self,
        collaborators: tuple[MagicMock, MagicMock],
    ) -> None:
        agent, calendar = collaborators
        context = AgentAuthorizationContext(trusted_automation_enabled=True)

        with pytest.raises(AgentAuthorizationError, match="requires explicit human approval"):
            make_workflow(agent, calendar).publish(make_publish_request(), context)
        calendar.publish_class_brief.assert_not_called()

    def test_approved_publish_calls_existing_calendar_gate(
        self,
        collaborators: tuple[MagicMock, MagicMock],
    ) -> None:
        agent, calendar = collaborators
        request = make_publish_request()
        context = AgentAuthorizationContext(approved=True, approved_by="course-director")

        result = make_workflow(agent, calendar).publish(request, context)

        assert result.calendar_result.event_id == "event_123"
        assert result.capability_decision.allowed is True
        assert result.capability_decision.requested_autonomy == AutonomyLevel.EXECUTE_WITH_APPROVAL
        assert "course-director" in result.capability_decision.reason
        calendar.publish_class_brief.assert_called_once_with(
            semester_id=request.draft.brief.semester_id,
            course_code=request.draft.brief.course_code,
            class_date=request.draft.brief.class_date,
            brief=request.draft.brief,
            time_min=request.time_min,
            time_max=request.time_max,
            reminders_minutes=request.reminders_minutes,
            authorized=True,
        )

    def test_downstream_calendar_error_is_not_swallowed(
        self,
        collaborators: tuple[MagicMock, MagicMock],
    ) -> None:
        agent, calendar = collaborators
        calendar.publish_class_brief.side_effect = RuntimeError("downstream gate")
        context = AgentAuthorizationContext(approved=True, approved_by="course-director")

        with pytest.raises(RuntimeError, match="downstream gate"):
            make_workflow(agent, calendar).publish(make_publish_request(), context)
