"""Tests for reviewed Teaching Coach publication request contracts."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from medsemiotics.domain.academic_state import TopicProgressStatus
from medsemiotics.domain.agents import (
    AgentCapabilityDecision,
    AgentPillar,
    AutonomyLevel,
)
from medsemiotics.domain.coaching import CoachingBrief
from medsemiotics.domain.teaching_coach import (
    TeachingCoachDraftResult,
    TeachingCoachPublishRequest,
)
from medsemiotics.domain.teaching_position import TeachingPaceStatus, TeachingPosition


def make_draft() -> TeachingCoachDraftResult:
    """Build a coherent allowed draft for publication tests."""
    return TeachingCoachDraftResult(
        brief=CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 9, 1),
            topic_id="coordination-cerebellum",
            topic_title="Coordinación y cerebelo",
            learning_objectives=["Distinguir patrones de ataxia."],
        ),
        teaching_position=TeachingPosition(
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
        ),
        topic_status=TopicProgressStatus.NOT_STARTED,
        context_notes=["Priorizar objetivos esenciales."],
        capability_decision=AgentCapabilityDecision(
            allowed=True,
            agent=AgentPillar.COACHING,
            capability_id="coaching.class-brief",
            requested_autonomy=AutonomyLevel.DRAFT,
            requires_approval=False,
            reason="DRAFT is within the declared capability range.",
        ),
    )


def make_publish_request(**updates: object) -> TeachingCoachPublishRequest:
    """Build a valid reviewed publication request."""
    tz = ZoneInfo("America/Guayaquil")
    values: dict[str, object] = {
        "draft": make_draft(),
        "time_min": datetime(2026, 9, 1, 0, 0, tzinfo=tz),
        "time_max": datetime(2026, 9, 2, 0, 0, tzinfo=tz),
        "reminders_minutes": [60, 15, 60],
        "requested_by": "course-director",
    }
    values.update(updates)
    return TeachingCoachPublishRequest(**values)  # type: ignore[arg-type]


class TestTeachingCoachPublishRequest:
    """Verify draft provenance, scope, and execution-window invariants."""

    def test_valid_request_normalizes_reminders(self) -> None:
        request = make_publish_request()
        assert request.reminders_minutes == [15, 60]

    def test_tampered_brief_scope_is_rejected(self) -> None:
        draft = make_draft()
        altered = draft.model_copy(
            update={"brief": draft.brief.model_copy(update={"course_code": "GASTRO"})}
        )
        with pytest.raises(ValidationError, match="does not match its authoritative"):
            make_publish_request(draft=altered)

    def test_tampered_topic_is_rejected(self) -> None:
        draft = make_draft()
        altered = draft.model_copy(
            update={"brief": draft.brief.model_copy(update={"topic_id": "cranial-nerves"})}
        )
        with pytest.raises(ValidationError, match="does not match its authoritative"):
            make_publish_request(draft=altered)

    def test_denied_draft_decision_is_rejected(self) -> None:
        draft = make_draft()
        denied = draft.capability_decision.model_copy(update={"allowed": False})
        altered = draft.model_copy(update={"capability_decision": denied})
        with pytest.raises(ValidationError, match="lacks an allowed"):
            make_publish_request(draft=altered)

    def test_wrong_capability_provenance_is_rejected(self) -> None:
        draft = make_draft()
        wrong = draft.capability_decision.model_copy(
            update={"capability_id": "coaching.calendar-brief-publish"}
        )
        altered = draft.model_copy(update={"capability_decision": wrong})
        with pytest.raises(ValidationError, match="lacks an allowed"):
            make_publish_request(draft=altered)

    @pytest.mark.parametrize("invalid_reminder", [0, -1, 40321, True])
    def test_invalid_reminders_are_rejected(self, invalid_reminder: object) -> None:
        with pytest.raises(ValidationError, match="between 1 and 40320"):
            make_publish_request(reminders_minutes=[invalid_reminder])

    def test_publication_window_must_include_class_date(self) -> None:
        tz = ZoneInfo("America/Guayaquil")
        with pytest.raises(ValidationError, match="must fall within"):
            make_publish_request(
                time_min=datetime(2026, 9, 2, 0, 0, tzinfo=tz),
                time_max=datetime(2026, 9, 3, 0, 0, tzinfo=tz),
            )
