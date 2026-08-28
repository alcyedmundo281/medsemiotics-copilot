"""Unit tests for teaching position resolution and pacing logic."""

from datetime import date

import pytest

from medsemiotics.domain.exceptions import AcademicStateError
from medsemiotics.domain.schedule import (
    ClassMeetingRule,
    ClassWeekday,
    CourseTeachingSchedule,
)
from medsemiotics.domain.syllabus import SyllabusPlan, SyllabusTopic
from medsemiotics.domain.teaching_log import (
    CoverageStatus,
    TeachingSession,
    TeachingSessionTopic,
)
from medsemiotics.domain.teaching_position import TeachingPaceStatus
from medsemiotics.services.teaching_position import resolve_teaching_position


class TestTeachingPositionResolution:
    """Test suite for resolve_teaching_position deterministic logic."""

    @pytest.fixture
    def five_topic_syllabus(self) -> SyllabusPlan:
        """5-topic syllabus for NEURO."""
        return SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="topic-1", planned_order=1, required=True),
                SyllabusTopic(topic_id="topic-2", planned_order=2, required=True),
                SyllabusTopic(topic_id="topic-3", planned_order=3, required=True),
                SyllabusTopic(topic_id="topic-4", planned_order=4, required=True),
                SyllabusTopic(topic_id="topic-5", planned_order=5, required=True),
            ],
        )

    @pytest.fixture
    def august_schedule(self) -> CourseTeachingSchedule:
        """Schedule with classes on Tuesdays and Thursdays in August 2026."""
        # Aug 2026 classes:
        # Aug 4 (Tue) -> session 1
        # Aug 6 (Thu) -> session 2
        # Aug 11 (Tue) -> session 3
        # Aug 13 (Thu) -> session 4
        # Aug 18 (Tue) -> session 5
        # Aug 20 (Thu) -> session 6
        return CourseTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=True,
            teaching_start_date=date(2026, 8, 1),
            teaching_end_date=date(2026, 8, 31),
            meeting_rules=[
                ClassMeetingRule(weekday=ClassWeekday.TUESDAY),
                ClassMeetingRule(weekday=ClassWeekday.THURSDAY),
            ],
        )

    def test_disabled_schedule_returns_unavailable(
        self, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Verify disabled schedule produces TeachingPaceStatus.UNAVAILABLE."""
        disabled_schedule = CourseTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=False,
            teaching_start_date=date(2026, 8, 1),
            teaching_end_date=date(2026, 8, 31),
            meeting_rules=[ClassMeetingRule(weekday=ClassWeekday.TUESDAY)],
        )

        pos = resolve_teaching_position(
            target_date=date(2026, 8, 15),
            schedule=disabled_schedule,
            syllabus=five_topic_syllabus,
            sessions=[],
        )
        assert pos.pace_status == TeachingPaceStatus.UNAVAILABLE
        assert pos.is_class_date is False
        assert pos.expected_session_count == 0
        assert pos.current_topic_id is None
        assert pos.topic_delta is None

    def test_before_first_class_not_started(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Verify evaluation date before first scheduled class yields not_started."""
        pos = resolve_teaching_position(
            target_date=date(2026, 8, 2),  # Sunday before Aug 4 first class
            schedule=august_schedule,
            syllabus=five_topic_syllabus,
            sessions=[],
        )
        assert pos.pace_status == TeachingPaceStatus.NOT_STARTED
        assert pos.is_class_date is False
        assert pos.expected_session_count == 0
        assert pos.actual_session_count == 0
        assert pos.expected_topic_order is None
        assert pos.current_topic_id == "topic-1"
        assert pos.topic_delta == 0

    def test_example_a_on_track(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Example A:

        5 planned topics
        target date corresponds to expected session 3 (Aug 11)
        topics 1 and 2 completed
        -> on_track (delta = 0).
        """
        sessions = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 4),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="topic-1", status=CoverageStatus.COMPLETED)],
            ),
            TeachingSession(
                session_id="s2",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 6),
                sequence_number=2,
                topics=[TeachingSessionTopic(topic_id="topic-2", status=CoverageStatus.COMPLETED)],
            ),
        ]

        pos = resolve_teaching_position(
            target_date=date(2026, 8, 11),  # Aug 11 is session 3
            schedule=august_schedule,
            syllabus=five_topic_syllabus,
            sessions=sessions,
        )

        assert pos.is_class_date is True
        assert pos.expected_session_count == 3
        assert pos.actual_session_count == 2
        assert pos.expected_topic_order == 3
        assert pos.current_topic_id == "topic-3"
        assert pos.topic_delta == 0
        assert pos.pace_status == TeachingPaceStatus.ON_TRACK

    def test_example_b_behind(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Example B:

        expected topic order = 4 (Aug 13)
        only topic 1 completed
        -> behind (delta = -2).
        """
        sessions = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 4),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="topic-1", status=CoverageStatus.COMPLETED)],
            ),
        ]

        pos = resolve_teaching_position(
            target_date=date(2026, 8, 13),  # Session 4
            schedule=august_schedule,
            syllabus=five_topic_syllabus,
            sessions=sessions,
        )

        assert pos.expected_topic_order == 4
        assert pos.current_topic_id == "topic-2"
        assert pos.topic_delta == -2
        assert pos.pace_status == TeachingPaceStatus.BEHIND

    def test_example_c_ahead(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Example C:

        expected topic order = 2 (Aug 6)
        topics 1 and 2 already completed
        -> ahead (delta = 1).
        """
        sessions = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 4),
                sequence_number=1,
                topics=[
                    TeachingSessionTopic(topic_id="topic-1", status=CoverageStatus.COMPLETED),
                    TeachingSessionTopic(topic_id="topic-2", status=CoverageStatus.COMPLETED),
                ],
            ),
        ]

        pos = resolve_teaching_position(
            target_date=date(2026, 8, 6),  # Session 2
            schedule=august_schedule,
            syllabus=five_topic_syllabus,
            sessions=sessions,
        )

        assert pos.expected_topic_order == 2
        assert pos.current_topic_id == "topic-3"
        assert pos.topic_delta == 1
        assert pos.pace_status == TeachingPaceStatus.AHEAD

    def test_all_required_completed_returns_complete(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Verify pace_status is COMPLETE when all syllabus topics are completed."""
        sessions = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 4),
                sequence_number=1,
                topics=[
                    TeachingSessionTopic(topic_id=f"topic-{i}", status=CoverageStatus.COMPLETED)
                    for i in range(1, 6)
                ],
            ),
        ]

        pos = resolve_teaching_position(
            target_date=date(2026, 8, 6),
            schedule=august_schedule,
            syllabus=five_topic_syllabus,
            sessions=sessions,
        )

        assert pos.pace_status == TeachingPaceStatus.COMPLETE
        assert pos.current_topic_id is None

    def test_future_sessions_ignored(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Verify sessions recorded with dates after target_date do not affect position."""
        sessions = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 4),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="topic-1", status=CoverageStatus.COMPLETED)],
            ),
            TeachingSession(
                session_id="future_s",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 20),
                sequence_number=2,
                topics=[TeachingSessionTopic(topic_id="topic-2", status=CoverageStatus.COMPLETED)],
            ),
        ]

        pos = resolve_teaching_position(
            target_date=date(2026, 8, 6),  # Prior to future session on Aug 20
            schedule=august_schedule,
            syllabus=five_topic_syllabus,
            sessions=sessions,
        )

        assert pos.actual_session_count == 1  # Only s1 counted
        assert pos.current_topic_id == "topic-2"  # topic-2 not completed yet on Aug 6

    def test_scope_validation_mismatch_raises_error(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Verify mismatch between schedule and syllabus raises AcademicStateError."""
        gastro_syllabus = SyllabusPlan(
            semester_id="2026-2",
            course_code="GASTRO",
            topics=[SyllabusTopic(topic_id="gastro-intro", planned_order=1)],
        )

        with pytest.raises(AcademicStateError, match="Scope mismatch"):
            resolve_teaching_position(
                target_date=date(2026, 8, 4),
                schedule=august_schedule,  # NEURO
                syllabus=gastro_syllabus,  # GASTRO
                sessions=[],
            )

    def test_session_scope_mismatch_raises_error(
        self, august_schedule: CourseTeachingSchedule, five_topic_syllabus: SyllabusPlan
    ) -> None:
        """Verify mismatch in session semester or course raises AcademicStateError."""
        wrong_session = TeachingSession(
            session_id="s1",
            semester_id="2026-2",
            course_code="GASTRO",  # Wrong course
            session_date=date(2026, 8, 4),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="topic-1", status=CoverageStatus.COMPLETED)],
        )

        with pytest.raises(AcademicStateError, match="Scope mismatch in teaching session"):
            resolve_teaching_position(
                target_date=date(2026, 8, 4),
                schedule=august_schedule,
                syllabus=five_topic_syllabus,
                sessions=[wrong_session],
            )
