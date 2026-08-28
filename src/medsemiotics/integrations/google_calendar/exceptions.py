"""Exceptions for Google Calendar external integration boundary."""

from medsemiotics.domain.exceptions import MedSemioticsError


class GoogleCalendarError(MedSemioticsError):
    """Base exception for Google Calendar integration errors."""


class GoogleCalendarAuthError(GoogleCalendarError):
    """Raised when authentication or token acquisition fails."""


class GoogleCalendarReadError(GoogleCalendarError):
    """Raised when fetching calendar list or events from Google Calendar fails."""


class GoogleCalendarMappingError(GoogleCalendarError):
    """Raised when a raw Google Calendar event fails mapping to OperationalCalendarEvent."""
