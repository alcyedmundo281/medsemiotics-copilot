"""Unit tests for effective schedule domain models."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from medsemiotics.domain.effective_schedule import (
    EffectiveClassEvent,
    EffectiveClassSource,
    EffectiveClassStatus,
    EffectiveTeachingSchedule,
)


class TestEffectiveClassEvent:
    """Test suite for EffectiveClassEvent validation."""

    @pytest.fixture
    def guayaquil_tz(self) -> ZoneInfo:
        return ZoneInfo("America/Guayaquil")

    def test_valid_event_without_times(self) -> None:
        """Verify valid event without start/end timestamps."""
        event = EffectiveClassEvent(
            date=date(2026, 8, 4),
            semester_id="2026-2",
            course_code="NEURO",
            source=EffectiveClassSource.BASELINE,
            status=EffectiveClassStatus.SCHEDULED,
        )
        assert event.date == date(2026, 8, 4)
        assert event.semester_id == "2026-2"
        assert event.course_code == "NEURO"
        assert event.source == EffectiveClassSource.BASELINE
        assert event.status == EffectiveClassStatus.SCHEDULED
        assert event.start is None
        assert event.end is None

    def test_valid_event_with_matching_times(self, guayaquil_tz: ZoneInfo) -> None:
        """Verify valid event with aligned timezone-aware timestamps."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)

        event = EffectiveClassEvent(
            date=date(2026, 8, 4),
            semester_id="2026-2",
            course_code="NEURO",
            source=EffectiveClassSource.BASELINE_AND_CALENDAR,
            status=EffectiveClassStatus.SCHEDULED,
            calendar_event_id="cal_evt_1",
            title="Clase de Neurología",
            start=start,
            end=end,
        )
        assert event.start == start
        assert event.end == end
        assert event.calendar_event_id == "cal_evt_1"
        assert event.title == "Clase de Neurología"

    def test_mismatched_date_and_start_rejected(self, guayaquil_tz: ZoneInfo) -> None:
        """Verify event date not matching start.date() raises ValidationError."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)

        with pytest.raises(ValidationError, match="does not match start timestamp date"):
            EffectiveClassEvent(
                date=date(2026, 8, 5),  # Mismatch!
                semester_id="2026-2",
                course_code="NEURO",
                source=EffectiveClassSource.BASELINE,
                status=EffectiveClassStatus.SCHEDULED,
                start=start,
                end=end,
            )

    def test_naive_datetime_rejected(self) -> None:
        """Verify naive datetime raises ValidationError."""
        with pytest.raises(ValidationError, match="must be timezone-aware"):
            EffectiveClassEvent(
                date=date(2026, 8, 4),
                semester_id="2026-2",
                course_code="NEURO",
                source=EffectiveClassSource.BASELINE,
                status=EffectiveClassStatus.SCHEDULED,
                start=datetime(2026, 8, 4, 8, 0),  # Naive!
                end=datetime(2026, 8, 4, 10, 0),
            )

    def test_one_timestamp_missing_rejected(self, guayaquil_tz: ZoneInfo) -> None:
        """Verify setting start without end raises ValidationError."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        with pytest.raises(ValidationError, match="requires both start and end"):
            EffectiveClassEvent(
                date=date(2026, 8, 4),
                semester_id="2026-2",
                course_code="NEURO",
                source=EffectiveClassSource.BASELINE,
                status=EffectiveClassStatus.SCHEDULED,
                start=start,
                end=None,
            )


class TestEffectiveTeachingSchedule:
    """Test suite for EffectiveTeachingSchedule."""

    @pytest.fixture
    def sample_schedule(self) -> EffectiveTeachingSchedule:
        tz = ZoneInfo("America/Guayaquil")
        return EffectiveTeachingSchedule(
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
                    start=datetime(2026, 8, 4, 10, 0, tzinfo=tz),
                    end=datetime(2026, 8, 4, 12, 0, tzinfo=tz),
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 11),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE_AND_CALENDAR,
                    status=EffectiveClassStatus.CANCELLED,
                    title="Feriado",
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 14),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.CALENDAR,
                    status=EffectiveClassStatus.MAKEUP,
                    start=datetime(2026, 8, 14, 14, 0, tzinfo=tz),
                    end=datetime(2026, 8, 14, 16, 0, tzinfo=tz),
                ),
            ],
        )

    def test_class_dates_filters_cancelled(
        self, sample_schedule: EffectiveTeachingSchedule
    ) -> None:
        """Verify class_dates includes scheduled and makeup, but excludes cancelled."""
        dates = sample_schedule.class_dates
        assert dates == [date(2026, 8, 4), date(2026, 8, 14)]
        assert date(2026, 8, 11) not in dates

    def test_is_class_date(self, sample_schedule: EffectiveTeachingSchedule) -> None:
        """Verify is_class_date accurately returns True/False."""
        assert sample_schedule.is_class_date(date(2026, 8, 4)) is True
        assert sample_schedule.is_class_date(date(2026, 8, 11)) is False
        assert sample_schedule.is_class_date(date(2026, 8, 14)) is True
        assert sample_schedule.is_class_date(date(2026, 8, 20)) is False

    def test_events_through_and_class_dates_through(
        self, sample_schedule: EffectiveTeachingSchedule
    ) -> None:
        """Verify filtering events and class dates through target date."""
        events_thru = sample_schedule.events_through(date(2026, 8, 11))
        assert len(events_thru) == 2
        assert [e.date for e in events_thru] == [date(2026, 8, 4), date(2026, 8, 11)]

        dates_thru = sample_schedule.class_dates_through(date(2026, 8, 11))
        assert dates_thru == [date(2026, 8, 4)]
