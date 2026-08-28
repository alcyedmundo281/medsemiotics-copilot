"""Unit tests for GoogleCalendarReader client using mocks."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.integrations.google_calendar.client import GoogleCalendarReader
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarReadError,
)


class TestGoogleCalendarReader:
    """Test suite for GoogleCalendarReader."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def reader(self, mock_service: MagicMock) -> GoogleCalendarReader:
        return GoogleCalendarReader(mock_service, default_timezone=ZoneInfo("America/Lima"))

    def test_list_calendars_with_pagination(
        self, reader: GoogleCalendarReader, mock_service: MagicMock
    ) -> None:
        """Verify list_calendars paginates across multiple pages."""
        # Page 1 response
        mock_req_1 = MagicMock()
        mock_req_1.execute.return_value = {
            "items": [
                {"id": "cal_1", "summary": "Main Calendar", "primary": True, "selected": True},
            ],
            "nextPageToken": "page2_token",
        }

        # Page 2 response
        mock_req_2 = MagicMock()
        mock_req_2.execute.return_value = {
            "items": [
                {"id": "cal_2", "summary": "Secondary Calendar", "primary": False, "selected": False},
            ],
        }

        mock_service.calendarList().list.side_effect = [mock_req_1, mock_req_2]

        calendars = reader.list_calendars()
        assert len(calendars) == 2
        assert calendars[0].calendar_id == "cal_1"
        assert calendars[0].primary is True
        assert calendars[1].calendar_id == "cal_2"
        assert calendars[1].primary is False

    def test_list_events_with_pagination_and_deterministic_order(
        self, reader: GoogleCalendarReader, mock_service: MagicMock
    ) -> None:
        """Verify list_events filters cancelled events, paginates, and sorts deterministically."""
        # Events returned in jumbled order across pages
        mock_req_1 = MagicMock()
        mock_req_1.execute.return_value = {
            "items": [
                {
                    "id": "evt_b",
                    "summary": "Event B",
                    "start": {"dateTime": "2026-08-04T14:00:00-05:00"},
                    "end": {"dateTime": "2026-08-04T16:00:00-05:00"},
                    "status": "confirmed",
                },
                {
                    "id": "evt_cancelled",
                    "summary": "Cancelled Event",
                    "start": {"dateTime": "2026-08-04T12:00:00-05:00"},
                    "end": {"dateTime": "2026-08-04T13:00:00-05:00"},
                    "status": "cancelled",
                },
            ],
            "nextPageToken": "token2",
        }

        mock_req_2 = MagicMock()
        mock_req_2.execute.return_value = {
            "items": [
                {
                    "id": "evt_a",
                    "summary": "Event A",
                    "start": {"dateTime": "2026-08-04T10:00:00-05:00"},
                    "end": {"dateTime": "2026-08-04T12:00:00-05:00"},
                    "status": "confirmed",
                },
            ],
        }

        mock_service.events().list.side_effect = [mock_req_1, mock_req_2]

        tz = ZoneInfo("America/Lima")
        events = reader.list_events(
            calendar_id="cal_1",
            time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
            time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
        )

        assert len(events) == 2
        # Deterministic sorting: evt_a (10:00) before evt_b (14:00)
        assert events[0].event_id == "evt_a"
        assert events[1].event_id == "evt_b"

    def test_list_events_naive_datetime_rejected(self, reader: GoogleCalendarReader) -> None:
        """Verify naive time_min or time_max raises GoogleCalendarReadError."""
        tz = ZoneInfo("UTC")
        with pytest.raises(GoogleCalendarReadError, match="must be timezone-aware"):
            reader.list_events(
                calendar_id="cal_1",
                time_min=datetime(2026, 8, 1, 0, 0),  # Naive!
                time_max=datetime(2026, 8, 31, 0, 0, tzinfo=tz),
            )

    def test_list_events_time_min_after_time_max_rejected(self, reader: GoogleCalendarReader) -> None:
        """Verify time_min >= time_max raises GoogleCalendarReadError."""
        tz = ZoneInfo("UTC")
        with pytest.raises(GoogleCalendarReadError, match="must be strictly before time_max"):
            reader.list_events(
                calendar_id="cal_1",
                time_min=datetime(2026, 8, 31, 0, 0, tzinfo=tz),
                time_max=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
            )

    def test_list_events_api_error_wrapped(
        self, reader: GoogleCalendarReader, mock_service: MagicMock
    ) -> None:
        """Verify underlying API exceptions are wrapped into GoogleCalendarReadError."""
        mock_service.events().list.side_effect = RuntimeError("Google API network socket error")

        tz = ZoneInfo("UTC")
        with pytest.raises(GoogleCalendarReadError, match="Failed to retrieve events"):
            reader.list_events(
                calendar_id="cal_1",
                time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
                time_max=datetime(2026, 8, 31, 0, 0, tzinfo=tz),
            )
