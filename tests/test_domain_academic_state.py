"""Unit tests for academic state domain models (TopicProgress, CourseAcademicState)."""

from datetime import date

import pytest
from pydantic import ValidationError

from medsemiotics.domain.academic_state import (
    CourseAcademicState,
    TopicProgress,
    TopicProgressStatus,
)


class TestTopicProgressDomainModel:
    """Test suite for TopicProgress validation and invariants."""

    def test_valid_not_started(self) -> None:
        """Verify valid not_started topic without dates and 0 session count."""
        prog = TopicProgress(
            topic_id="neuro-intro",
            planned_order=1,
            required=True,
            status=TopicProgressStatus.NOT_STARTED,
            session_count=0,
        )
        assert prog.topic_id == "neuro-intro"
        assert prog.planned_order == 1
        assert prog.required is True
        assert prog.status == TopicProgressStatus.NOT_STARTED
        assert prog.first_taught_date is None
        assert prog.last_taught_date is None
        assert prog.session_count == 0

    def test_valid_in_progress_with_dates(self) -> None:
        """Verify valid in_progress topic with identical or ordered dates."""
        prog = TopicProgress(
            topic_id="stroke",
            planned_order=2,
            required=True,
            status=TopicProgressStatus.IN_PROGRESS,
            first_taught_date=date(2026, 8, 20),
            last_taught_date=date(2026, 8, 25),
            session_count=2,
        )
        assert prog.first_taught_date == date(2026, 8, 20)
        assert prog.last_taught_date == date(2026, 8, 25)
        assert prog.session_count == 2

    def test_zero_session_count_with_dates_rejected(self) -> None:
        """Verify error when session_count=0 but dates are provided."""
        with pytest.raises(ValidationError, match="session_count=0 but non-null teaching dates"):
            TopicProgress(
                topic_id="neuro-intro",
                planned_order=1,
                required=True,
                status=TopicProgressStatus.NOT_STARTED,
                first_taught_date=date(2026, 8, 20),
                session_count=0,
            )

    def test_positive_session_count_with_missing_dates_rejected(self) -> None:
        """Verify error when session_count>0 but dates are missing."""
        with pytest.raises(ValidationError, match="missing dates"):
            TopicProgress(
                topic_id="neuro-intro",
                planned_order=1,
                required=True,
                status=TopicProgressStatus.IN_PROGRESS,
                first_taught_date=date(2026, 8, 20),
                last_taught_date=None,
                session_count=1,
            )

    def test_invalid_date_ordering_rejected(self) -> None:
        """Verify error when first_taught_date is later than last_taught_date."""
        with pytest.raises(ValidationError, match="first_taught_date .* > last_taught_date"):
            TopicProgress(
                topic_id="neuro-intro",
                planned_order=1,
                required=True,
                status=TopicProgressStatus.IN_PROGRESS,
                first_taught_date=date(2026, 8, 25),
                last_taught_date=date(2026, 8, 20),
                session_count=2,
            )

    @pytest.mark.parametrize("invalid_order", [0, -1, -5])
    def test_invalid_planned_order(self, invalid_order: int) -> None:
        """Verify planned_order must be >= 1."""
        with pytest.raises(ValidationError):
            TopicProgress(
                topic_id="neuro-intro",
                planned_order=invalid_order,
                required=True,
                status=TopicProgressStatus.NOT_STARTED,
            )

    @pytest.mark.parametrize("invalid_count", [-1, -10])
    def test_invalid_session_count(self, invalid_count: int) -> None:
        """Verify session_count must be >= 0."""
        with pytest.raises(ValidationError):
            TopicProgress(
                topic_id="neuro-intro",
                planned_order=1,
                required=True,
                status=TopicProgressStatus.NOT_STARTED,
                session_count=invalid_count,
            )


class TestCourseAcademicStateDomainModel:
    """Test suite for CourseAcademicState properties and queries."""

    @pytest.fixture
    def sample_state(self) -> CourseAcademicState:
        """Fixture producing a multi-status course academic state."""
        return CourseAcademicState(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                TopicProgress(
                    topic_id="t3",
                    planned_order=3,
                    required=True,
                    status=TopicProgressStatus.NOT_STARTED,
                ),
                TopicProgress(
                    topic_id="t1",
                    planned_order=1,
                    required=True,
                    status=TopicProgressStatus.COMPLETED,
                    first_taught_date=date(2026, 8, 15),
                    last_taught_date=date(2026, 8, 15),
                    session_count=1,
                ),
                TopicProgress(
                    topic_id="t2",
                    planned_order=2,
                    required=True,
                    status=TopicProgressStatus.IN_PROGRESS,
                    first_taught_date=date(2026, 8, 18),
                    last_taught_date=date(2026, 8, 18),
                    session_count=1,
                ),
                TopicProgress(
                    topic_id="t4_elective",
                    planned_order=4,
                    required=False,
                    status=TopicProgressStatus.SKIPPED,
                    first_taught_date=date(2026, 8, 20),
                    last_taught_date=date(2026, 8, 20),
                    session_count=1,
                ),
            ],
        )

    def test_ordered_topics_sorting(self, sample_state: CourseAcademicState) -> None:
        """Verify ordered_topics returns topics sorted by planned_order."""
        ordered = sample_state.ordered_topics
        assert [t.topic_id for t in ordered] == ["t1", "t2", "t3", "t4_elective"]
        assert [t.planned_order for t in ordered] == [1, 2, 3, 4]

    def test_status_filtering_properties(self, sample_state: CourseAcademicState) -> None:
        """Verify status filter properties."""
        assert [t.topic_id for t in sample_state.completed_topics] == ["t1"]
        assert [t.topic_id for t in sample_state.in_progress_topics] == ["t2"]
        assert [t.topic_id for t in sample_state.not_started_topics] == ["t3"]
        assert [t.topic_id for t in sample_state.skipped_topics] == ["t4_elective"]

    def test_required_topics_filtering(self, sample_state: CourseAcademicState) -> None:
        """Verify required_topics and completed_required_topics."""
        assert [t.topic_id for t in sample_state.required_topics] == ["t1", "t2", "t3"]
        assert [t.topic_id for t in sample_state.completed_required_topics] == ["t1"]

    def test_next_required_topic_selection(self, sample_state: CourseAcademicState) -> None:
        """Verify next_required_topic picks first in_progress or not_started required topic."""
        next_topic = sample_state.next_required_topic
        assert next_topic is not None
        assert next_topic.topic_id == "t2"
        assert next_topic.planned_order == 2

    def test_next_required_topic_skips_skipped_topics(self) -> None:
        """Verify skipped topics are not returned as next_required_topic."""
        state = CourseAcademicState(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                TopicProgress(
                    topic_id="t1",
                    planned_order=1,
                    required=True,
                    status=TopicProgressStatus.COMPLETED,
                    first_taught_date=date(2026, 8, 15),
                    last_taught_date=date(2026, 8, 15),
                    session_count=1,
                ),
                TopicProgress(
                    topic_id="t2",
                    planned_order=2,
                    required=True,
                    status=TopicProgressStatus.SKIPPED,
                    first_taught_date=date(2026, 8, 18),
                    last_taught_date=date(2026, 8, 18),
                    session_count=1,
                ),
                TopicProgress(
                    topic_id="t3",
                    planned_order=3,
                    required=True,
                    status=TopicProgressStatus.NOT_STARTED,
                ),
            ],
        )
        assert state.next_required_topic is not None
        assert state.next_required_topic.topic_id == "t3"

    def test_next_required_topic_none_when_all_completed(self) -> None:
        """Verify next_required_topic is None when all required topics are completed."""
        state = CourseAcademicState(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                TopicProgress(
                    topic_id="t1",
                    planned_order=1,
                    required=True,
                    status=TopicProgressStatus.COMPLETED,
                    first_taught_date=date(2026, 8, 15),
                    last_taught_date=date(2026, 8, 15),
                    session_count=1,
                ),
            ],
        )
        assert state.next_required_topic is None

    def test_completion_ratio_calculation(self, sample_state: CourseAcademicState) -> None:
        """Verify completion_ratio computes unrounded float."""
        # 1 completed out of 3 required topics = 1/3 ~ 0.3333333333333333
        assert sample_state.completion_ratio == pytest.approx(1.0 / 3.0)

    def test_completion_ratio_zero_required_topics(self) -> None:
        """Verify completion_ratio is 1.0 when there are no required topics."""
        state = CourseAcademicState(
            semester_id="2026-2",
            course_code="GASTRO",
            topics=[
                TopicProgress(
                    topic_id="elective-1",
                    planned_order=1,
                    required=False,
                    status=TopicProgressStatus.NOT_STARTED,
                )
            ],
        )
        assert state.completion_ratio == 1.0
