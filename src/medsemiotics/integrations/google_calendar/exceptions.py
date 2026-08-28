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


class GoogleCalendarWriteError(GoogleCalendarError):
    """Raised when creating, updating, or patching a Google Calendar event fails."""


class GoogleCalendarOwnershipError(GoogleCalendarError):
    """Raised when event ownership integrity fails or multiple managed events conflict."""
