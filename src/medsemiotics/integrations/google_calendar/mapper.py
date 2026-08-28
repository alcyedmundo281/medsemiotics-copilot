"""Mapper for translating raw Google Calendar API JSON responses to domain models."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from medsemiotics.domain.calendar import OperationalCalendarEvent
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarMappingError,
)


def map_google_event(
    raw_event: object,
    *,
    calendar_id: str,
    default_timezone: ZoneInfo,
) -> OperationalCalendarEvent:
    """Map a raw Google Calendar event dictionary to an OperationalCalendarEvent domain model.

    Args:
        raw_event: Dictionary representing a single Google Calendar event resource.
        calendar_id: Identifier of the Google Calendar containing the event.
        default_timezone: ZoneInfo timezone applied to all-day date boundaries.

    Returns:
        Validated OperationalCalendarEvent instance.

    Raises:
        GoogleCalendarMappingError: If raw_event is malformed, missing required fields, or invalid.
    """
    if not isinstance(raw_event, dict):
        msg = f"Expected dict for raw_event, got {type(raw_event).__name__}"
        raise GoogleCalendarMappingError(msg)

    event_id = raw_event.get("id")
    if not event_id or not isinstance(event_id, str) or not event_id.strip():
        msg = "Google Calendar event is missing a non-empty string 'id' field."
        raise GoogleCalendarMappingError(msg)

    summary = raw_event.get("summary")
    title = summary.strip() if isinstance(summary, str) and summary.strip() else "(No title)"

    start_info = raw_event.get("start")
    end_info = raw_event.get("end")

    if not isinstance(start_info, dict) or not isinstance(end_info, dict):
        msg = f"Event '{event_id}' is missing valid start or end object."
        raise GoogleCalendarMappingError(msg)

    try:
        if "dateTime" in start_info:
            start_raw = start_info["dateTime"]
            end_raw = end_info.get("dateTime")
            if not isinstance(start_raw, str) or not isinstance(end_raw, str):
                msg = f"Event '{event_id}' has non-string dateTime field."
                raise GoogleCalendarMappingError(msg)

            start_dt = datetime.fromisoformat(start_raw)
            end_dt = datetime.fromisoformat(end_raw)

            if start_dt.tzinfo is None or start_dt.tzinfo.utcoffset(start_dt) is None:
                msg = f"Event '{event_id}' start datetime is timezone-naive: {start_raw}"
                raise GoogleCalendarMappingError(msg)

            if end_dt.tzinfo is None or end_dt.tzinfo.utcoffset(end_dt) is None:
                msg = f"Event '{event_id}' end datetime is timezone-naive: {end_raw}"
                raise GoogleCalendarMappingError(msg)

            all_day = False
        elif "date" in start_info:
            start_date_raw = start_info["date"]
            end_date_raw = end_info.get("date")
            if not isinstance(start_date_raw, str) or not isinstance(end_date_raw, str):
                msg = f"Event '{event_id}' has non-string date field."
                raise GoogleCalendarMappingError(msg)

            start_d = date.fromisoformat(start_date_raw)
            end_d = date.fromisoformat(end_date_raw)

            # Google Calendar all-day end dates are exclusive
            start_dt = datetime.combine(start_d, time.min, tzinfo=default_timezone)
            end_dt = datetime.combine(end_d, time.min, tzinfo=default_timezone)
            all_day = True
        else:
            msg = (
                f"Event '{event_id}' has unrecognized start format "
                "(neither dateTime nor date found)."
            )
            raise GoogleCalendarMappingError(msg)

        return OperationalCalendarEvent(
            event_id=event_id,
            calendar_id=calendar_id,
            title=title,
            start=start_dt,
            end=end_dt,
            all_day=all_day,
            description=raw_event.get("description"),
            location=raw_event.get("location"),
            status=raw_event.get("status"),
            source="google_calendar",
        )
    except (ValueError, KeyError, TypeError, ValidationError) as err:
        msg = f"Failed to map Google Calendar event '{event_id}': {err}"
        raise GoogleCalendarMappingError(msg) from err
