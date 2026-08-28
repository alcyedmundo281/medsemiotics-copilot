"""Google Calendar read-only integration package."""

from medsemiotics.integrations.google_calendar.auth import (
    CALENDAR_READONLY_SCOPE,
    get_calendar_credentials,
)
from medsemiotics.integrations.google_calendar.client import (
    CalendarDescriptor,
    GoogleCalendarReader,
)
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarAuthError,
    GoogleCalendarError,
    GoogleCalendarMappingError,
    GoogleCalendarReadError,
)
from medsemiotics.integrations.google_calendar.mapper import map_google_event

__all__ = [
    "CALENDAR_READONLY_SCOPE",
    "CalendarDescriptor",
    "GoogleCalendarAuthError",
    "GoogleCalendarError",
    "GoogleCalendarMappingError",
    "GoogleCalendarReadError",
    "GoogleCalendarReader",
    "get_calendar_credentials",
    "map_google_event",
]
