"""Unit tests for calendar domain models (OperationalCalendarEvent, CourseCalendarConfig)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from medsemiotics.domain.calendar import (
    CourseCalendarConfig,
    OperationalCalendarEvent,
)


class TestOperationalCalendarEvent:
    """Test suite for OperationalCalendarEvent validation."""

    def test_valid_timezone_aware_event(self) -> None:
        """Verify valid event with timezone-aware start and end."""
        tz = ZoneInfo("America/Lima")
        start = datetime(2026, 8, 4, 10, 0, tzinfo=tz)
        end = datetime(2026, 8, 4, 12, 0, tzinfo=tz)

        event = OperationalCalendarEvent(
            event_id="evt_001",
            calendar_id="cal_primary",
            title="Neurología Clínica",
            start=start,
            end=end,
            all_day=False,
            location="Aula Magna",
            description="Clase inaugural",
            status="confirmed",
        )

        assert event.event_id == "evt_001"
        assert event.calendar_id == "cal_primary"
        assert event.title == "Neurología Clínica"
        assert event.start == start
        assert event.end == end
        assert event.all_day is False
        assert event.location == "Aula Magna"
        assert event.description == "Clase inaugural"
        assert event.status == "confirmed"
        assert event.source == "google_calendar"

    def test_naive_start_datetime_rejected(self) -> None:
        """Verify naive start datetime raises ValidationError."""
        tz = ZoneInfo("UTC")
        with pytest.raises(ValidationError, match="start datetime must be timezone-aware"):
            OperationalCalendarEvent(
                event_id="evt_001",
                calendar_id="cal_primary",
                title="Clase",
                start=datetime(2026, 8, 4, 10, 0),  # Naive!
                end=datetime(2026, 8, 4, 12, 0, tzinfo=tz),
                all_day=False,
            )

    def test_naive_end_datetime_rejected(self) -> None:
        """Verify naive end datetime raises ValidationError."""
        tz = ZoneInfo("UTC")
        with pytest.raises(ValidationError, match="end datetime must be timezone-aware"):
            OperationalCalendarEvent(
                event_id="evt_001",
                calendar_id="cal_primary",
                title="Clase",
                start=datetime(2026, 8, 4, 10, 0, tzinfo=tz),
                end=datetime(2026, 8, 4, 12, 0),  # Naive!
                all_day=False,
            )

    def test_start_greater_or_equal_end_rejected(self) -> None:
        """Verify start >= end raises ValidationError."""
        tz = ZoneInfo("UTC")
        with pytest.raises(ValidationError, match="must be strictly before end"):
            OperationalCalendarEvent(
                event_id="evt_001",
                calendar_id="cal_primary",
                title="Clase",
                start=datetime(2026, 8, 4, 12, 0, tzinfo=tz),
                end=datetime(2026, 8, 4, 10, 0, tzinfo=tz),
                all_day=False,
            )

    def test_empty_required_fields_rejected(self) -> None:
        """Verify empty event_id, calendar_id, or title are rejected."""
        tz = ZoneInfo("UTC")
        start = datetime(2026, 8, 4, 10, 0, tzinfo=tz)
        end = datetime(2026, 8, 4, 12, 0, tzinfo=tz)

        with pytest.raises(ValidationError):
            OperationalCalendarEvent(
                event_id="   ",
                calendar_id="cal_primary",
                title="Clase",
                start=start,
                end=end,
                all_day=False,
            )

    def test_optional_fields_normalization(self) -> None:
        """Verify blank optional strings normalize to None."""
        tz = ZoneInfo("UTC")
        event = OperationalCalendarEvent(
            event_id="evt_001",
            calendar_id="cal_primary",
            title="Clase",
            start=datetime(2026, 8, 4, 10, 0, tzinfo=tz),
            end=datetime(2026, 8, 4, 12, 0, tzinfo=tz),
            all_day=False,
            description="   ",
            location="",
            status=None,
        )
        assert event.description is None
        assert event.location is None
        assert event.status is None


class TestCourseCalendarConfig:
    """Test suite for CourseCalendarConfig validation."""

    def test_disabled_config_without_calendar_id_valid(self) -> None:
        """Verify disabled config with null calendar_id is valid."""
        cfg = CourseCalendarConfig(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=False,
            calendar_id=None,
            aliases=["NEURO", "Neurología"],
        )
        assert cfg.enabled is False
        assert cfg.calendar_id is None
        assert cfg.aliases == ["NEURO", "Neurología"]

    def test_enabled_config_requires_calendar_id(self) -> None:
        """Verify enabled config without calendar_id raises ValidationError."""
        with pytest.raises(ValidationError, match="enabled but calendar_id is missing"):
            CourseCalendarConfig(
                semester_id="2026-2",
                course_code="NEURO",
                enabled=True,
                calendar_id=None,
                aliases=["NEURO"],
            )

    def test_case_insensitive_duplicate_aliases_rejected(self) -> None:
        """Verify duplicate aliases with different casing are rejected."""
        with pytest.raises(ValidationError, match="Duplicate alias found"):
            CourseCalendarConfig(
                semester_id="2026-2",
                course_code="NEURO",
                enabled=False,
                aliases=["Neuro", "NEURO"],
            )

    def test_empty_aliases_list_rejected(self) -> None:
        """Verify empty aliases list is rejected."""
        with pytest.raises(ValidationError):
            CourseCalendarConfig(
                semester_id="2026-2",
                course_code="NEURO",
                enabled=False,
                aliases=[],
            )
