"""Unit tests for Google Calendar event mapper."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarMappingError,
)
from medsemiotics.integrations.google_calendar.mapper import map_google_event


class TestGoogleCalendarMapper:
    """Test suite for map_google_event."""

    @pytest.fixture
    def default_tz(self) -> ZoneInfo:
        return ZoneInfo("America/Lima")

    def test_map_timed_event_success(self, default_tz: ZoneInfo) -> None:
        """Verify standard timed Google event is mapped with timezone preserved."""
        raw_event = {
            "id": "evt_timed_123",
            "summary": "Clase Neurología - Cefaleas",
            "description": "Revisión de cefalea tensional y migraña",
            "location": "Hospital Central Aula 4",
            "status": "confirmed",
            "start": {"dateTime": "2026-08-04T10:00:00-05:00"},
            "end": {"dateTime": "2026-08-04T12:00:00-05:00"},
        }

        event = map_google_event(raw_event, calendar_id="c_primary", default_timezone=default_tz)
        assert event.event_id == "evt_timed_123"
        assert event.calendar_id == "c_primary"
        assert event.title == "Clase Neurología - Cefaleas"
        assert event.all_day is False
        assert event.start == datetime(2026, 8, 4, 10, 0, tzinfo=default_tz)
        assert event.end == datetime(2026, 8, 4, 12, 0, tzinfo=default_tz)
        assert event.description == "Revisión de cefalea tensional y migraña"
        assert event.location == "Hospital Central Aula 4"
        assert event.status == "confirmed"

    def test_map_all_day_event_success(self, default_tz: ZoneInfo) -> None:
        """Verify all-day Google event maps exclusive end date using default_timezone."""
        raw_event = {
            "id": "evt_allday_456",
            "summary": "Feriado Académico",
            "start": {"date": "2026-08-10"},
            "end": {"date": "2026-08-11"},  # Google end date is exclusive
        }

        event = map_google_event(raw_event, calendar_id="c_academic", default_timezone=default_tz)
        assert event.event_id == "evt_allday_456"
        assert event.all_day is True
        assert event.start == datetime(2026, 8, 10, 0, 0, tzinfo=default_tz)
        assert event.end == datetime(2026, 8, 11, 0, 0, tzinfo=default_tz)

    def test_missing_event_id_raises_mapping_error(self, default_tz: ZoneInfo) -> None:
        """Verify missing id raises GoogleCalendarMappingError."""
        raw_event = {
            "summary": "Sin ID",
            "start": {"dateTime": "2026-08-04T10:00:00Z"},
            "end": {"dateTime": "2026-08-04T12:00:00Z"},
        }
        with pytest.raises(GoogleCalendarMappingError, match=r"missing .* 'id' field"):
            map_google_event(raw_event, calendar_id="c1", default_timezone=default_tz)

    def test_naive_datetime_raises_mapping_error(self, default_tz: ZoneInfo) -> None:
        """Verify naive ISO string raises GoogleCalendarMappingError."""
        raw_event = {
            "id": "evt_naive",
            "summary": "Naive Event",
            "start": {"dateTime": "2026-08-04T10:00:00"},
            "end": {"dateTime": "2026-08-04T12:00:00"},
        }
        with pytest.raises(GoogleCalendarMappingError, match="timezone-naive"):
            map_google_event(raw_event, calendar_id="c1", default_timezone=default_tz)

    def test_malformed_datetime_string_raises_mapping_error(self, default_tz: ZoneInfo) -> None:
        """Verify malformed datetime string raises GoogleCalendarMappingError."""
        raw_event = {
            "id": "evt_bad_dt",
            "summary": "Bad Datetime",
            "start": {"dateTime": "not-a-datetime"},
            "end": {"dateTime": "2026-08-04T12:00:00Z"},
        }
        with pytest.raises(GoogleCalendarMappingError, match="Failed to map Google Calendar event"):
            map_google_event(raw_event, calendar_id="c1", default_timezone=default_tz)

    def test_non_dict_event_raises_mapping_error(self, default_tz: ZoneInfo) -> None:
        """Verify non-dict input raises GoogleCalendarMappingError."""
        with pytest.raises(GoogleCalendarMappingError, match="Expected dict for raw_event"):
            map_google_event("not a dict", calendar_id="c1", default_timezone=default_tz)  # type: ignore[arg-type]

    def test_missing_start_or_end_dict_raises_mapping_error(self, default_tz: ZoneInfo) -> None:
        """Verify missing start or end dictionary raises GoogleCalendarMappingError."""
        raw_event = {
            "id": "evt_no_end",
            "summary": "No end dict",
            "start": {"dateTime": "2026-08-04T10:00:00Z"},
        }
        with pytest.raises(GoogleCalendarMappingError, match="missing valid start or end object"):
            map_google_event(raw_event, calendar_id="c1", default_timezone=default_tz)

    def test_unrecognized_start_format_raises_mapping_error(self, default_tz: ZoneInfo) -> None:
        """Verify start dict without dateTime or date raises GoogleCalendarMappingError."""
        raw_event = {
            "id": "evt_bad_keys",
            "summary": "Bad keys",
            "start": {"other": "value"},
            "end": {"other": "value"},
        }
        with pytest.raises(GoogleCalendarMappingError, match="unrecognized start format"):
            map_google_event(raw_event, calendar_id="c1", default_timezone=default_tz)
