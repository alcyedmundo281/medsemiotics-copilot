"""Unit tests for teaching position resolution from reconciled effective schedules."""

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.domain.effective_schedule import (
    EffectiveClassEvent,
    EffectiveClassSource,
    EffectiveClassStatus,
    EffectiveTeachingSchedule,
)
from medsemiotics.domain.syllabus import SyllabusPlan, SyllabusTopic
from medsemiotics.domain.teaching_log import (
    CoverageStatus,
    TeachingSession,
    TeachingSessionTopic,
)
from medsemiotics.domain.teaching_position import TeachingPaceStatus
from medsemiotics.services.effective_schedule_service import (
    EffectiveScheduleService,
)
from medsemiotics.services.effective_teaching_day_service import (
    EffectiveTeachingDayService,
)
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_log_repository import TeachingLogRepository
from medsemiotics.services.teaching_position import (
    resolve_teaching_position_from_effective_schedule,
)


class TestEffectiveTeachingPosition:
    """Test suite for resolve_teaching_position_from_effective_schedule."""

    @pytest.fixture
    def syllabus(self) -> SyllabusPlan:
        return SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="t1", planned_order=1, required=True),
                SyllabusTopic(topic_id="t2", planned_order=2, required=True),
                SyllabusTopic(topic_id="t3", planned_order=3, required=True),
                SyllabusTopic(topic_id="t4", planned_order=4, required=True),
            ],
        )

    def test_reconciled_cancelled_class_reduces_expected_session_count(
        self, syllabus: SyllabusPlan
    ) -> None:
        """Verify cancelled class on Aug 11 does not count toward count on Aug 13."""
        # Aug 4 (scheduled), Aug 11 (cancelled), Aug 13 (scheduled)
        effective = EffectiveTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[
                EffectiveClassEvent(
                    date=date(2026, 8, 4),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 11),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE_AND_CALENDAR,
                    status=EffectiveClassStatus.CANCELLED,
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 13),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                ),
            ],
        )

        pos = resolve_teaching_position_from_effective_schedule(
            target_date=date(2026, 8, 13),
            effective_schedule=effective,
            syllabus=syllabus,
            sessions=[],
        )

        # Only Aug 4 and Aug 13 count -> expected_session_count is 2 (NOT 3!)
        assert pos.expected_session_count == 2
        assert pos.expected_topic_order == 2
        assert pos.is_class_date is True

    def test_reconciled_makeup_class_increases_expected_session_count(
        self, syllabus: SyllabusPlan
    ) -> None:
        """Verify makeup class on Aug 14 increases expected_session_count."""
        effective = EffectiveTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[
                EffectiveClassEvent(
                    date=date(2026, 8, 4),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 6),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 14),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.CALENDAR,
                    status=EffectiveClassStatus.MAKEUP,
                ),
            ],
        )

        pos = resolve_teaching_position_from_effective_schedule(
            target_date=date(2026, 8, 14),
            effective_schedule=effective,
            syllabus=syllabus,
            sessions=[],
        )

        assert pos.expected_session_count == 3
        assert pos.expected_topic_order == 3
        assert pos.is_class_date is True

    def test_calendar_only_schedule_establishes_expected_sessions(
        self, syllabus: SyllabusPlan
    ) -> None:
        """Verify effective schedule with only calendar events calculates pacing correctly."""
        effective = EffectiveTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[
                EffectiveClassEvent(
                    date=date(2026, 8, 5),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.CALENDAR,
                    status=EffectiveClassStatus.MAKEUP,
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 12),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.CALENDAR,
                    status=EffectiveClassStatus.MAKEUP,
                ),
            ],
        )

        session_1 = TeachingSession(
            session_id="s1",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 5),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="t1", status=CoverageStatus.COMPLETED)],
        )

        pos = resolve_teaching_position_from_effective_schedule(
            target_date=date(2026, 8, 12),
            effective_schedule=effective,
            syllabus=syllabus,
            sessions=[session_1],
        )

        assert pos.expected_session_count == 2
        assert pos.expected_topic_order == 2
        assert pos.actual_session_count == 1
        assert pos.current_topic_id == "t2"
        # expected_topic_order = 2 -> expected completed = 1; actual completed = 1 (t1) -> delta 0
        assert pos.pace_status == TeachingPaceStatus.ON_TRACK
        assert pos.topic_delta == 0

    def test_empty_effective_schedule_returns_unavailable(self, syllabus: SyllabusPlan) -> None:
        """Verify empty effective schedule returns pace_status UNAVAILABLE."""
        empty_schedule = EffectiveTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[],
        )
        pos = resolve_teaching_position_from_effective_schedule(
            target_date=date(2026, 8, 4),
            effective_schedule=empty_schedule,
            syllabus=syllabus,
            sessions=[],
        )
        assert pos.pace_status == TeachingPaceStatus.UNAVAILABLE
        assert pos.is_class_date is False
        assert pos.expected_session_count == 0

    def test_scope_mismatch_raises_academic_state_error(self, syllabus: SyllabusPlan) -> None:
        """Verify mismatched semester, course, or session raises AcademicStateError."""
        from medsemiotics.domain.exceptions import AcademicStateError

        mismatched_schedule = EffectiveTeachingSchedule(
            semester_id="2026-1",  # Mismatch!
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[],
        )
        with pytest.raises(AcademicStateError, match="Scope mismatch"):
            resolve_teaching_position_from_effective_schedule(
                target_date=date(2026, 8, 4),
                effective_schedule=mismatched_schedule,
                syllabus=syllabus,
                sessions=[],
            )

        valid_schedule = EffectiveTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[
                EffectiveClassEvent(
                    date=date(2026, 8, 4),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                )
            ],
        )
        mismatched_session = TeachingSession(
            session_id="s_bad",
            semester_id="2026-1",  # Mismatch!
            course_code="NEURO",
            session_date=date(2026, 8, 4),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="t1", status=CoverageStatus.COMPLETED)],
        )
        with pytest.raises(AcademicStateError, match="Scope mismatch"):
            resolve_teaching_position_from_effective_schedule(
                target_date=date(2026, 8, 4),
                effective_schedule=valid_schedule,
                syllabus=syllabus,
                sessions=[mismatched_session],
            )


class TestEffectiveTeachingDayService:
    """Test suite for EffectiveTeachingDayService orchestration."""

    def test_get_position_and_topic_for_date(self) -> None:
        """Verify EffectiveTeachingDayService coordinates services and returns position."""
        mock_eff_service = MagicMock(spec=EffectiveScheduleService)
        mock_syll_repo = MagicMock(spec=SyllabusRepository)
        mock_log_repo = MagicMock(spec=TeachingLogRepository)

        effective_sched = EffectiveTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[
                EffectiveClassEvent(
                    date=date(2026, 8, 4),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                )
            ],
        )
        mock_eff_service.get_effective_schedule.return_value = effective_sched

        syllabus = SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[SyllabusTopic(topic_id="neuro-intro", planned_order=1, required=True)],
        )
        mock_syll_repo.get.return_value = syllabus
        mock_log_repo.get_sessions.return_value = []

        day_service = EffectiveTeachingDayService(
            effective_schedule_service=mock_eff_service,
            syllabus_repository=mock_syll_repo,
            teaching_log_repository=mock_log_repo,
        )

        tz = ZoneInfo("America/Guayaquil")
        pos = day_service.get_position(
            semester_id="2026-2",
            course_code="NEURO",
            target_date=date(2026, 8, 4),
            time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
            time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
        )

        assert pos.is_class_date is True
        assert pos.expected_session_count == 1
        assert pos.current_topic_id == "neuro-intro"

        topic_id = day_service.get_topic_for_date(
            semester_id="2026-2",
            course_code="NEURO",
            target_date=date(2026, 8, 4),
            time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
            time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
        )
        assert topic_id == "neuro-intro"
