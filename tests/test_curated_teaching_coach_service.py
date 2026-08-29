"""Tests for catalog-backed, draft-only Teaching Coach orchestration."""

from unittest.mock import MagicMock

import pytest

from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.domain.exceptions import (
    TeachingCoachTopicError,
    TeachingGuideDisabledError,
)
from medsemiotics.domain.teaching_coach import TeachingCoachDraftResult
from medsemiotics.services.curated_teaching_coach import CuratedTeachingCoachService
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository
from tests.test_domain_teaching_coach import make_curated_request, make_guide


def make_service(
    repository: MagicMock,
    agent: MagicMock,
) -> CuratedTeachingCoachService:
    """Build the service with controlled read-only collaborators."""
    return CuratedTeachingCoachService(
        teaching_guide_repository=repository,
        teaching_coach_agent=agent,
    )


class TestCuratedTeachingCoachService:
    """Verify catalog loading remains separate from deterministic agent reasoning."""

    def test_loads_guide_and_delegates_complete_request(self) -> None:
        repository = MagicMock(spec=TeachingGuideRepository)
        agent = MagicMock(spec=TeachingCoachAgent)
        guide = make_guide()
        expected = MagicMock(spec=TeachingCoachDraftResult)
        repository.get_guide.return_value = guide
        agent.draft_class_brief.return_value = expected
        request = make_curated_request()

        result = make_service(repository, agent).draft_class_brief(request)

        assert result is expected
        repository.get_guide.assert_called_once_with(
            semester_id="2026-2",
            course_code="NEURO",
            topic_id="coordination-cerebellum",
        )
        agent_request = agent.draft_class_brief.call_args.args[0]
        assert agent_request.semester_id == request.semester_id
        assert agent_request.course_code == request.course_code
        assert agent_request.class_date == request.class_date
        assert agent_request.time_min == request.time_min
        assert agent_request.time_max == request.time_max
        assert agent_request.guide is guide
        assert agent_request.requested_by == request.requested_by

    def test_disabled_catalog_fails_closed_before_agent(self) -> None:
        repository = MagicMock(spec=TeachingGuideRepository)
        agent = MagicMock(spec=TeachingCoachAgent)
        repository.get_guide.side_effect = TeachingGuideDisabledError("disabled")

        with pytest.raises(TeachingGuideDisabledError, match="disabled"):
            make_service(repository, agent).draft_class_brief(make_curated_request())

        agent.draft_class_brief.assert_not_called()

    def test_agent_topic_mismatch_is_not_swallowed(self) -> None:
        repository = MagicMock(spec=TeachingGuideRepository)
        agent = MagicMock(spec=TeachingCoachAgent)
        repository.get_guide.return_value = make_guide()
        agent.draft_class_brief.side_effect = TeachingCoachTopicError("current topic mismatch")

        with pytest.raises(TeachingCoachTopicError, match="current topic mismatch"):
            make_service(repository, agent).draft_class_brief(make_curated_request())
