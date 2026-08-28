"""Google Calendar event writer for managing MedSemiotics-owned teaching events."""

from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from medsemiotics.domain.coaching import (
    CalendarPublishAction,
    CalendarPublishRequest,
    CalendarPublishResult,
    ManagedCalendarEvent,
)
from medsemiotics.domain.constants import (
    MANAGED_TRUE_VALUE,
    PROP_CLASS_DATE,
    PROP_COURSE_CODE,
    PROP_MANAGED,
    PROP_SEMESTER_ID,
)
from medsemiotics.integrations.google_calendar.auth import (
    get_calendar_write_credentials,
)
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarOwnershipError,
    GoogleCalendarWriteError,
)


def _parse_managed_event(calendar_id: str, item: dict[str, Any]) -> ManagedCalendarEvent:
    """Parse a raw Google API event dict into a ManagedCalendarEvent."""
    event_id = str(item.get("id", ""))
    summary = str(item.get("summary", ""))
    description = str(item.get("description", ""))
    location = item.get("location")

    start_obj = item.get("start", {})
    end_obj = item.get("end", {})

    start_str = start_obj.get("dateTime") or start_obj.get("date")
    end_str = end_obj.get("dateTime") or end_obj.get("date")

    if not start_str or not end_str:
        msg = f"Managed event '{event_id}' is missing start or end timestamp object."
        raise GoogleCalendarWriteError(msg)

    start_dt = datetime.fromisoformat(start_str)
    end_dt = datetime.fromisoformat(end_str)

    # Ensure timezone awareness
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=ZoneInfo("UTC"))
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=ZoneInfo("UTC"))

    # Parse reminders
    reminders_minutes: list[int] = []
    reminders_obj = item.get("reminders", {})
    if reminders_obj.get("useDefault") is False:
        for override in reminders_obj.get("overrides", []):
            if isinstance(override, dict) and override.get("method") == "popup":
                try:
                    reminders_minutes.append(int(override["minutes"]))
                except (KeyError, ValueError, TypeError):
                    pass

    # Parse private metadata
    extended_props = item.get("extendedProperties", {})
    private_props = extended_props.get("private", {}) if isinstance(extended_props, dict) else {}
    metadata = {str(k): str(v) for k, v in private_props.items()}

    return ManagedCalendarEvent(
        calendar_id=calendar_id,
        event_id=event_id,
        title=summary,
        description=description,
        start=start_dt,
        end=end_dt,
        location=str(location).strip() if location else None,
        reminders_minutes=sorted(set(reminders_minutes)),
        metadata=metadata,
    )


class GoogleCalendarWriter:
    """Write client for managing, creating, and patching MedSemiotics-owned calendar events."""

    def __init__(
        self,
        service: Resource | None = None,
        *,
        credentials_path: Path | str | None = None,
        token_path: Path | str | None = None,
        interactive: bool = False,
    ) -> None:
        """Initialize writer with an optional mock service or construct via OAuth credentials."""
        if service is not None:
            self._service = service
        else:
            creds = get_calendar_write_credentials(
                credentials_path=credentials_path,
                token_path=token_path,
                interactive=interactive,
            )
            self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def find_managed_event(
        self,
        *,
        calendar_id: str,
        semester_id: str,
        course_code: str,
        class_date: date,
    ) -> ManagedCalendarEvent | None:
        """Query Google Calendar for an existing event owned by MedSemiotics via private extended properties.

        Args:
            calendar_id: Google Calendar identifier.
            semester_id: Semester identifier.
            course_code: Course code.
            class_date: Target class meeting date.

        Returns:
            ManagedCalendarEvent if exactly one matching event is found; None if zero matches.

        Raises:
            GoogleCalendarOwnershipError: If more than one managed event matches the ownership criteria.
            GoogleCalendarWriteError: If Google API query fails.
        """
        prop_query = [
            f"{PROP_MANAGED}={MANAGED_TRUE_VALUE}",
            f"{PROP_SEMESTER_ID}={semester_id}",
            f"{PROP_COURSE_CODE}={course_code}",
            f"{PROP_CLASS_DATE}={class_date.isoformat()}",
        ]

        matched_items: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            try:
                request = self._service.events().list(
                    calendarId=calendar_id,
                    privateExtendedProperty=prop_query,
                    showDeleted=False,
                    singleEvents=True,
                    pageToken=page_token,
                )
                response = request.execute()
            except HttpError as err:
                msg = f"Failed to query managed events in calendar '{calendar_id}': {err}"
                raise GoogleCalendarWriteError(msg) from err
            except Exception as err:
                msg = f"Unexpected error querying managed events in calendar '{calendar_id}': {err}"
                raise GoogleCalendarWriteError(msg) from err

            for item in response.get("items", []):
                if item.get("status") != "cancelled":
                    matched_items.append(item)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        if not matched_items:
            return None

        if len(matched_items) > 1:
            event_ids = [item.get("id", "unknown") for item in matched_items]
            msg = (
                f"Multiple managed events found for {course_code} ({semester_id}) on {class_date.isoformat()} "
                f"in calendar '{calendar_id}': {event_ids}. Ambiguous ownership."
            )
            raise GoogleCalendarOwnershipError(msg)

        return _parse_managed_event(calendar_id, matched_items[0])

    def publish(self, request: CalendarPublishRequest) -> CalendarPublishResult:
        """Publish a teaching briefing event to Google Calendar (create, update, or unchanged).

        Args:
            request: Validated CalendarPublishRequest.

        Returns:
            CalendarPublishResult specifying the calendar_id, event_id, and action performed.

        Raises:
            GoogleCalendarWriteError: If Google API mutation fails.
            GoogleCalendarOwnershipError: If multiple existing managed events conflict.
        """
        semester_id = request.metadata.get(PROP_SEMESTER_ID, "")
        course_code = request.metadata.get(PROP_COURSE_CODE, "")

        existing = self.find_managed_event(
            calendar_id=request.calendar_id,
            semester_id=semester_id,
            course_code=course_code,
            class_date=request.event_date,
        )

        reminders_body = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": m} for m in request.reminders_minutes],
        }

        if existing is None:
            # CREATE new event
            body: dict[str, Any] = {
                "summary": request.title,
                "description": request.description,
                "start": {"dateTime": request.start.isoformat()},
                "end": {"dateTime": request.end.isoformat()},
                "reminders": reminders_body,
                "extendedProperties": {
                    "private": request.metadata,
                },
            }
            if request.location is not None:
                body["location"] = request.location

            try:
                created = self._service.events().insert(
                    calendarId=request.calendar_id,
                    body=body,
                ).execute()
            except HttpError as err:
                msg = f"Failed to create teaching event in calendar '{request.calendar_id}': {err}"
                raise GoogleCalendarWriteError(msg) from err
            except Exception as err:
                msg = f"Unexpected error creating teaching event in calendar '{request.calendar_id}': {err}"
                raise GoogleCalendarWriteError(msg) from err

            event_id = str(created.get("id", ""))
            return CalendarPublishResult(
                calendar_id=request.calendar_id,
                event_id=event_id,
                action=CalendarPublishAction.CREATED,
            )

        # Compare existing vs requested fields owned by MedSemiotics
        title_matches = existing.title == request.title
        desc_matches = existing.description == request.description
        start_matches = existing.start == request.start
        end_matches = existing.end == request.end
        loc_matches = existing.location == request.location
        reminders_matches = existing.reminders_minutes == request.reminders_minutes
        metadata_matches = existing.metadata == request.metadata

        if (
            title_matches
            and desc_matches
            and start_matches
            and end_matches
            and loc_matches
            and reminders_matches
            and metadata_matches
        ):
            # UNCHANGED: no write call
            return CalendarPublishResult(
                calendar_id=request.calendar_id,
                event_id=existing.event_id,
                action=CalendarPublishAction.UNCHANGED,
            )

        # UPDATE via patch
        patch_body: dict[str, Any] = {
            "summary": request.title,
            "description": request.description,
            "start": {"dateTime": request.start.isoformat()},
            "end": {"dateTime": request.end.isoformat()},
            "reminders": reminders_body,
            "extendedProperties": {
                "private": request.metadata,
            },
        }
        if request.location is not None:
            patch_body["location"] = request.location

        try:
            self._service.events().patch(
                calendarId=request.calendar_id,
                eventId=existing.event_id,
                body=patch_body,
            ).execute()
        except HttpError as err:
            msg = f"Failed to patch teaching event '{existing.event_id}' in calendar '{request.calendar_id}': {err}"
            raise GoogleCalendarWriteError(msg) from err
        except Exception as err:
            msg = f"Unexpected error patching teaching event '{existing.event_id}': {err}"
            raise GoogleCalendarWriteError(msg) from err

        return CalendarPublishResult(
            calendar_id=request.calendar_id,
            event_id=existing.event_id,
            action=CalendarPublishAction.UPDATED,
        )
