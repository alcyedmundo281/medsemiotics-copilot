"""Tests for the automatic, read-only Teaching Coach preview workflow."""

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.domain.exceptions import (
    TeachingCoachNoClassError,
    TeachingCoachScopeError,
    TeachingCoachTopicError,
    TeachingGuideNotFoundError,
)
from medsemiotics.domain.teaching_coach import (
    TeachingCoachPreviewRequest,
)
from medsemiotics.domain.teaching_position import TeachingPaceStatus, TeachingPosition
from medsemiotics.services.curated_teaching_coach import CuratedTeachingCoachService
from medsemiotics.services.effective_teaching_day_service import EffectiveTeachingDayService
from medsemiotics.services.teaching_coach_preview import TeachingCoachPreviewService
from tests.test_domain_teaching_coach_publish import make_draft


@pytest.fixture
def preview_request() -> TeachingCoachPreviewRequest:
    """Build a normalized preview request with an explicit academic time window."""
    timezone = ZoneInfo("America/Guayaquil")
    return TeachingCoachPreviewRequest(
        semester_id="2026-2",
        course_code="neuro",
        class_date=date(2026, 9, 1),
        time_min=datetime(2026, 9, 1, 0, 0, tzinfo=timezone),
        time_max=datetime(2026, 9, 2, 0, 0, tzinfo=timezone),
        requested_by="course-director",
    )


@pytest.fixture
def position() -> TeachingPosition:
    """Return an active effective position with one automatically selectable topic."""
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


def make_service(
    position: TeachingPosition,
) -> tuple[TeachingCoachPreviewService, MagicMock, MagicMock]:
    """Build the preview workflow with controlled read-only collaborators."""
    day_service = MagicMock(spec=EffectiveTeachingDayService)
    day_service.get_position.return_value = position
    curated_service = MagicMock(spec=CuratedTeachingCoachService)
    curated_service.draft_class_brief.return_value = make_draft()
    service = TeachingCoachPreviewService(
        teaching_day_service=day_service,
        curated_teaching_coach_service=curated_service,
    )
    return service, day_service, curated_service


class TestTeachingCoachPreviewService:
    """Verify topic selection, rendering, and fail-closed preview behavior."""

    def test_selects_current_topic_and_renders_reviewable_preview(
        self,
        preview_request: TeachingCoachPreviewRequest,
        position: TeachingPosition,
    ) -> None:
        service, day_service, curated_service = make_service(position)

        result = service.preview_class_brief(preview_request)

        assert result.preview_title == "NEURO — Coordinación y cerebelo"
        assert "MEDSEMIOTICS TEACHING COPILOT" in result.preview_body
        assert "Tema:\nCoordinación y cerebelo" in result.preview_body
        day_service.get_position.assert_called_once_with(
            semester_id="2026-2",
            course_code="NEURO",
            target_date=date(2026, 9, 1),
            time_min=preview_request.time_min,
            time_max=preview_request.time_max,
        )
        curated_request = curated_service.draft_class_brief.call_args.args[0]
        assert curated_request.topic_id == "coordination-cerebellum"
        assert curated_request.requested_by == "course-director"

    def test_non_class_date_stops_before_curated_drafting(
        self,
        preview_request: TeachingCoachPreviewRequest,
        position: TeachingPosition,
    ) -> None:
        service, _day_service, curated_service = make_service(
            position.model_copy(update={"is_class_date": False})
        )

        with pytest.raises(TeachingCoachNoClassError, match="No active effective class"):
            service.preview_class_brief(preview_request)

        curated_service.draft_class_brief.assert_not_called()

    def test_complete_course_stops_when_no_topic_remains(
        self,
        preview_request: TeachingCoachPreviewRequest,
        position: TeachingPosition,
    ) -> None:
        service, _day_service, curated_service = make_service(
            position.model_copy(
                update={
                    "current_topic_id": None,
                    "pace_status": TeachingPaceStatus.COMPLETE,
                }
            )
        )

        with pytest.raises(TeachingCoachTopicError, match="No current topic"):
            service.preview_class_brief(preview_request)

        curated_service.draft_class_brief.assert_not_called()

    def test_cross_course_position_is_rejected(
        self,
        preview_request: TeachingCoachPreviewRequest,
        position: TeachingPosition,
    ) -> None:
        service, _day_service, curated_service = make_service(
            position.model_copy(update={"course_code": "GASTRO"})
        )

        with pytest.raises(TeachingCoachScopeError, match="position scope"):
            service.preview_class_brief(preview_request)

        curated_service.draft_class_brief.assert_not_called()

    def test_missing_current_guide_error_is_not_swallowed(
        self,
        preview_request: TeachingCoachPreviewRequest,
        position: TeachingPosition,
    ) -> None:
        service, _day_service, curated_service = make_service(position)
        curated_service.draft_class_brief.side_effect = TeachingGuideNotFoundError("missing guide")

        with pytest.raises(TeachingGuideNotFoundError, match="missing guide"):
            service.preview_class_brief(preview_request)


class TestTeachingCoachPreviewRequest:
    """Verify the mobile-facing preview input remains explicit and deterministic."""

    def test_normalizes_course_and_rejects_unknown_fields(
        self,
        preview_request: TeachingCoachPreviewRequest,
    ) -> None:
        assert preview_request.course_code == "NEURO"

        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            TeachingCoachPreviewRequest.model_validate(
                {**preview_request.model_dump(), "publish": True}
            )

    def test_rejects_naive_time_window(self) -> None:
        with pytest.raises(ValueError, match="time_min must be timezone-aware"):
            TeachingCoachPreviewRequest(
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 9, 1),
                time_min=datetime(2026, 9, 1, 0, 0),
                time_max=datetime(2026, 9, 2, 0, 0),
                requested_by="course-director",
            )
