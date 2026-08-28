"""Google Calendar integration package."""

from medsemiotics.integrations.google_calendar.auth import (
    CALENDAR_EVENTS_WRITE_SCOPE,
    CALENDAR_READONLY_SCOPE,
    get_calendar_credentials,
    get_calendar_write_credentials,
)
from medsemiotics.integrations.google_calendar.client import (
    CalendarDescriptor,
    GoogleCalendarReader,
)
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarAuthError,
    GoogleCalendarError,
    GoogleCalendarMappingError,
    GoogleCalendarOwnershipError,
    GoogleCalendarReadError,
    GoogleCalendarWriteError,
)
from medsemiotics.integrations.google_calendar.mapper import map_google_event
from medsemiotics.integrations.google_calendar.writer import GoogleCalendarWriter

__all__ = [
    "CALENDAR_EVENTS_WRITE_SCOPE",
    "CALENDAR_READONLY_SCOPE",
    "CalendarDescriptor",
    "GoogleCalendarAuthError",
    "GoogleCalendarError",
    "GoogleCalendarMappingError",
    "GoogleCalendarOwnershipError",
    "GoogleCalendarReadError",
    "GoogleCalendarReader",
    "GoogleCalendarWriteError",
    "GoogleCalendarWriter",
    "get_calendar_credentials",
    "get_calendar_write_credentials",
    "map_google_event",
]
