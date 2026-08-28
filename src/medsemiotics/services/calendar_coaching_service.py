"""Application service for publishing coaching briefings to Google Calendar."""

from collections.abc import Collection
from datetime import date, datetime

from medsemiotics.domain.coaching import CalendarPublishResult, CoachingBrief
from medsemiotics.domain.effective_schedule import EffectiveClassStatus
from medsemiotics.domain.exceptions import (
    CalendarConfigError,
    CalendarPublishPlanError,
    CalendarWriteAuthorizationError,
)
from medsemiotics.integrations.google_calendar.writer import GoogleCalendarWriter
from medsemiotics.services.calendar_config_repository import (
    CalendarConfigRepository,
)
from medsemiotics.services.calendar_publish_plan import (
    build_calendar_publish_request,
)
from medsemiotics.services.effective_schedule_service import (
    EffectiveScheduleService,
)
from medsemiotics.services.semester_repository import SemesterRepository


class CalendarCoachingService:
    """Service orchestrating authorized publishing of pedagogical briefs to Google Calendar."""

    def __init__(
        self,
        semester_repository: SemesterRepository,
        calendar_config_repository: CalendarConfigRepository,
        effective_schedule_service: EffectiveScheduleService,
        calendar_writer: GoogleCalendarWriter,
    ) -> None:
        """Initialize service with domain repositories and Google Calendar writer."""
        self._semester_repo = semester_repository
        self._calendar_config_repo = calendar_config_repository
        self._effective_schedule_service = effective_schedule_service
        self._calendar_writer = calendar_writer

    def publish_class_brief(
        self,
        *,
        semester_id: str,
        course_code: str,
        class_date: date,
        brief: CoachingBrief,
        time_min: datetime,
        time_max: datetime,
        reminders_minutes: Collection[int] = (),
        authorized: bool = False,
    ) -> CalendarPublishResult:
        """Publish or update a coaching briefing event in Google Calendar.

        Args:
            semester_id: Target semester identifier.
            course_code: Target course code.
            class_date: Date of the target class meeting.
            brief: Structured CoachingBrief content.
            time_min: Start boundary for calendar querying.
            time_max: End boundary for calendar querying.
            reminders_minutes: Optional popup reminder minutes.
            authorized: Explicit authorization flag required for write actions.

        Returns:
            CalendarPublishResult detailing the action taken.

        Raises:
            CalendarWriteAuthorizationError: If authorized is False.
            CalendarConfigError: If calendar config is disabled or calendar_id is missing.
            CalendarPublishPlanError: If no active class exists on class_date or class is cancelled.
        """
        if not authorized:
            msg = (
                "Calendar write operations require explicit authorization (authorized=True). "
                f"Attempted write for {course_code} on {class_date} was blocked."
            )
            raise CalendarWriteAuthorizationError(msg)

        semester = self._semester_repo.get(semester_id)
        calendar_config = self._calendar_config_repo.get(semester_id, course_code)

        if not calendar_config.enabled:
            msg = (
                f"Calendar integration is disabled for {course_code} ({semester_id}). "
                "Cannot publish coaching brief."
            )
            raise CalendarConfigError(msg)

        if not calendar_config.calendar_id:
            msg = (
                f"Calendar integration is enabled for {course_code} ({semester_id}) "
                "but calendar_id is missing or null."
            )
            raise CalendarConfigError(msg)

        effective_schedule = self._effective_schedule_service.get_effective_schedule(
            semester_id=semester_id,
            course_code=course_code,
            time_min=time_min,
            time_max=time_max,
        )

        matching_events = [e for e in effective_schedule.events if e.date == class_date]
        if not matching_events:
            msg = (
                f"No effective class event found on {class_date} for {course_code} ({semester_id}). "
                "Cannot publish coaching brief."
            )
            raise CalendarPublishPlanError(msg)

        if len(matching_events) > 1:
            msg = f"Multiple effective class events found on {class_date} for {course_code} ({semester_id})."
            raise CalendarPublishPlanError(msg)

        target_event = matching_events[0]
        if target_event.status == EffectiveClassStatus.CANCELLED:
            msg = f"Cannot publish coaching brief for cancelled class on {class_date} ({course_code})."
            raise CalendarPublishPlanError(msg)

        publish_request = build_calendar_publish_request(
            calendar_id=calendar_config.calendar_id,
            semester_timezone=semester.tz,
            class_event=target_event,
            brief=brief,
            reminders_minutes=reminders_minutes,
        )

        return self._calendar_writer.publish(publish_request)
