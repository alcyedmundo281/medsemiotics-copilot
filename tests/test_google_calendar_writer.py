"""Unit tests for GoogleCalendarWriter integration."""

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from medsemiotics.domain.coaching import (
    CalendarPublishAction,
    CalendarPublishRequest,
)
from medsemiotics.domain.constants import (
    MANAGED_TRUE_VALUE,
    PROP_CLASS_DATE,
    PROP_COURSE_CODE,
    PROP_MANAGED,
    PROP_SCHEMA_VERSION,
    PROP_SEMESTER_ID,
    SCHEMA_VERSION_VALUE,
)
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarOwnershipError,
    GoogleCalendarWriteError,
)
from medsemiotics.integrations.google_calendar.writer import GoogleCalendarWriter


class TestGoogleCalendarWriter:
    """Test suite for GoogleCalendarWriter."""

    @pytest.fixture
    def guayaquil_tz(self) -> ZoneInfo:
        return ZoneInfo("America/Guayaquil")

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def writer(self, mock_service: MagicMock) -> GoogleCalendarWriter:
        return GoogleCalendarWriter(service=mock_service)

    @pytest.fixture
    def publish_request(self, guayaquil_tz: ZoneInfo) -> CalendarPublishRequest:
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)
        metadata = {
            PROP_MANAGED: MANAGED_TRUE_VALUE,
            PROP_SEMESTER_ID: "2026-2",
            PROP_COURSE_CODE: "NEURO",
            PROP_CLASS_DATE: "2026-08-04",
            PROP_SCHEMA_VERSION: SCHEMA_VERSION_VALUE,
        }
        return CalendarPublishRequest(
            calendar_id="cal_neuro",
            event_date=date(2026, 8, 4),
            start=start,
            end=end,
            title="NEURO — Síndrome cerebeloso",
            description="Brief description",
            location="Aula 401",
            reminders_minutes=[15, 60],
            metadata=metadata,
        )

    def test_find_managed_event_zero_matches_returns_none(
        self, writer: GoogleCalendarWriter, mock_service: MagicMock
    ) -> None:
        """Verify find_managed_event returns None when no matching managed events exist."""
        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_list.execute.return_value = {"items": []}

        event = writer.find_managed_event(
            calendar_id="cal_neuro",
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
        )
        assert event is None

    def test_find_managed_event_single_match_returns_managed_event(
        self, writer: GoogleCalendarWriter, mock_service: MagicMock
    ) -> None:
        """Verify find_managed_event parses and returns existing managed event."""
        mock_item = {
            "id": "evt_existing_1",
            "summary": "NEURO — Síndrome cerebeloso",
            "description": "Brief description",
            "location": "Aula 401",
            "start": {"dateTime": "2026-08-04T08:00:00-05:00"},
            "end": {"dateTime": "2026-08-04T10:00:00-05:00"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 15},
                    {"method": "popup", "minutes": 60},
                ],
            },
            "extendedProperties": {
                "private": {
                    PROP_MANAGED: MANAGED_TRUE_VALUE,
                    PROP_SEMESTER_ID: "2026-2",
                    PROP_COURSE_CODE: "NEURO",
                    PROP_CLASS_DATE: "2026-08-04",
                    PROP_SCHEMA_VERSION: SCHEMA_VERSION_VALUE,
                }
            },
        }

        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_list.execute.return_value = {"items": [mock_item]}

        event = writer.find_managed_event(
            calendar_id="cal_neuro",
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
        )
        assert event is not None
        assert event.event_id == "evt_existing_1"
        assert event.title == "NEURO — Síndrome cerebeloso"
        assert event.reminders_minutes == [15, 60]

    def test_find_managed_event_multiple_matches_raises_ownership_error(
        self, writer: GoogleCalendarWriter, mock_service: MagicMock
    ) -> None:
        """Verify multiple managed events for same date raise GoogleCalendarOwnershipError."""
        mock_items = [
            {
                "id": "evt_1",
                "summary": "Event 1",
                "status": "confirmed",
                "start": {"dateTime": "2026-08-04T08:00:00Z"},
                "end": {"dateTime": "2026-08-04T10:00:00Z"},
            },
            {
                "id": "evt_2",
                "summary": "Event 2",
                "status": "confirmed",
                "start": {"dateTime": "2026-08-04T08:00:00Z"},
                "end": {"dateTime": "2026-08-04T10:00:00Z"},
            },
        ]
        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_list.execute.return_value = {"items": mock_items}

        with pytest.raises(GoogleCalendarOwnershipError, match="Multiple managed events found"):
            writer.find_managed_event(
                calendar_id="cal_neuro",
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 8, 4),
            )

    def test_publish_creates_event_when_none_exists(
        self,
        writer: GoogleCalendarWriter,
        mock_service: MagicMock,
        publish_request: CalendarPublishRequest,
    ) -> None:
        """Verify publishing creates a new event when no owned event exists."""
        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_list.execute.return_value = {"items": []}

        mock_insert = mock_events.insert.return_value
        mock_insert.execute.return_value = {"id": "created_evt_99"}

        result = writer.publish(publish_request)

        assert result.action == CalendarPublishAction.CREATED
        assert result.event_id == "created_evt_99"
        mock_events.insert.assert_called_once()
        insert_args = mock_events.insert.call_args[1]
        assert insert_args["calendarId"] == "cal_neuro"
        assert insert_args["body"]["summary"] == "NEURO — Síndrome cerebeloso"

    def test_publish_unchanged_when_existing_matches_identically(
        self,
        writer: GoogleCalendarWriter,
        mock_service: MagicMock,
        publish_request: CalendarPublishRequest,
    ) -> None:
        """Verify publishing returns UNCHANGED and skips write when existing event is identical."""
        mock_item = {
            "id": "evt_existing_1",
            "summary": publish_request.title,
            "description": publish_request.description,
            "location": publish_request.location,
            "start": {"dateTime": publish_request.start.isoformat()},
            "end": {"dateTime": publish_request.end.isoformat()},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 15},
                    {"method": "popup", "minutes": 60},
                ],
            },
            "extendedProperties": {
                "private": publish_request.metadata,
            },
        }

        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_list.execute.return_value = {"items": [mock_item]}

        result = writer.publish(publish_request)

        assert result.action == CalendarPublishAction.UNCHANGED
        assert result.event_id == "evt_existing_1"
        mock_events.insert.assert_not_called()
        mock_events.patch.assert_not_called()

    def test_publish_patches_event_when_content_differs(
        self,
        writer: GoogleCalendarWriter,
        mock_service: MagicMock,
        publish_request: CalendarPublishRequest,
    ) -> None:
        """Verify publishing patches existing event when description/title/metadata differs."""
        mock_item = {
            "id": "evt_existing_1",
            "summary": "Old Summary",  # Differs!
            "description": "Old Description",
            "location": publish_request.location,
            "start": {"dateTime": publish_request.start.isoformat()},
            "end": {"dateTime": publish_request.end.isoformat()},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 15},
                    {"method": "popup", "minutes": 60},
                ],
            },
            "extendedProperties": {
                "private": publish_request.metadata,
            },
        }

        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_list.execute.return_value = {"items": [mock_item]}

        mock_patch = mock_events.patch.return_value
        mock_patch.execute.return_value = {"id": "evt_existing_1"}

        result = writer.publish(publish_request)

        assert result.action == CalendarPublishAction.UPDATED
        assert result.event_id == "evt_existing_1"
        mock_events.patch.assert_called_once()
        patch_args = mock_events.patch.call_args[1]
        assert patch_args["eventId"] == "evt_existing_1"
        assert patch_args["body"]["summary"] == publish_request.title

    def test_publish_http_error_wrapped(
        self,
        writer: GoogleCalendarWriter,
        mock_service: MagicMock,
        publish_request: CalendarPublishRequest,
    ) -> None:
        """Verify Google API HttpError is wrapped in GoogleCalendarWriteError."""
        mock_events = mock_service.events.return_value
        mock_list = mock_events.list.return_value
        mock_list.execute.side_effect = HttpError(Response({"status": "403"}), b"Forbidden")

        with pytest.raises(GoogleCalendarWriteError, match="Failed to query managed events"):
            writer.publish(publish_request)
