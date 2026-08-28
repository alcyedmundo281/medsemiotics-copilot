"""Google Calendar API reader client and descriptor models."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from medsemiotics.domain.calendar import OperationalCalendarEvent
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarMappingError,
    GoogleCalendarReadError,
)
from medsemiotics.integrations.google_calendar.mapper import map_google_event


class CalendarDescriptor(BaseModel):
    """Metadata descriptor for an accessible Google Calendar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calendar_id: str = Field(description="Google Calendar identifier")
    name: str = Field(description="Display summary or name of the calendar")
    primary: bool = Field(default=False, description="Whether this is the user's primary calendar")
    selected: bool | None = Field(
        default=None, description="Whether the calendar is selected in the UI"
    )


class GoogleCalendarReader:
    """Read-only client for retrieving calendars and events via Google Calendar API v3."""

    def __init__(
        self,
        service: Any,
        *,
        default_timezone: ZoneInfo | None = None,
    ) -> None:
        """Initialize with an authenticated Google API service resource.

        Args:
            service: Google Calendar API resource (e.g. build('calendar', 'v3', ...)).
            default_timezone: Timezone applied when converting all-day date boundaries.
        """
        self._service = service
        self._default_timezone = default_timezone or ZoneInfo("UTC")

    def list_calendars(self) -> list[CalendarDescriptor]:
        """Enumerate all calendars accessible to the authenticated account with full pagination.

        Returns:
            List of CalendarDescriptor models.

        Raises:
            GoogleCalendarReadError: If the Google API request fails.
        """
        calendars: list[CalendarDescriptor] = []
        page_token: str | None = None

        try:
            while True:
                request = self._service.calendarList().list(pageToken=page_token)
                response = request.execute()

                items = response.get("items", [])
                for item in items:
                    if isinstance(item, Mapping):
                        calendars.append(
                            CalendarDescriptor(
                                calendar_id=item["id"],
                                name=item.get("summary", "(Untitled)"),
                                primary=item.get("primary", False),
                                selected=item.get("selected"),
                            )
                        )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            return calendars
        except Exception as err:
            msg = f"Failed to list Google calendars: {err}"
            raise GoogleCalendarReadError(msg) from err

    def list_events(
        self,
        *,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[OperationalCalendarEvent]:
        """Fetch and map events from a calendar within a specified time range.

        Args:
            calendar_id: Target Google Calendar identifier.
            time_min: Start timestamp of the query window (must be timezone-aware).
            time_max: End timestamp of the query window (must be timezone-aware).

        Returns:
            List of OperationalCalendarEvent instances sorted by start timestamp and event_id.

        Raises:
            GoogleCalendarReadError: If query parameters are invalid or API calls fail.
            GoogleCalendarMappingError: If event parsing fails.
        """
        if time_min.tzinfo is None or time_min.tzinfo.utcoffset(time_min) is None:
            msg = f"time_min must be timezone-aware (got {time_min})."
            raise GoogleCalendarReadError(msg)

        if time_max.tzinfo is None or time_max.tzinfo.utcoffset(time_max) is None:
            msg = f"time_max must be timezone-aware (got {time_max})."
            raise GoogleCalendarReadError(msg)

        if time_min >= time_max:
            msg = f"time_min ({time_min}) must be strictly before time_max ({time_max})."
            raise GoogleCalendarReadError(msg)

        events: list[OperationalCalendarEvent] = []
        page_token: str | None = None

        try:
            while True:
                request = self._service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    showDeleted=False,
                    pageToken=page_token,
                )
                response = request.execute()

                items = response.get("items", [])
                for item in items:
                    if isinstance(item, Mapping):
                        if item.get("status") == "cancelled":
                            continue

                        mapped_event = map_google_event(
                            dict(item),
                            calendar_id=calendar_id,
                            default_timezone=self._default_timezone,
                        )
                        events.append(mapped_event)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        except GoogleCalendarMappingError:
            raise
        except Exception as err:
            msg = f"Failed to retrieve events for calendar '{calendar_id}': {err}"
            raise GoogleCalendarReadError(msg) from err

        return sorted(events, key=lambda e: (e.start, e.event_id))
