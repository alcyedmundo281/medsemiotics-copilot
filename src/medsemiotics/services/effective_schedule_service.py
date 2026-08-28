"""Application service orchestrating effective teaching schedule reconciliation."""

from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from medsemiotics.domain.calendar import OperationalCalendarEvent

from medsemiotics.domain.effective_schedule import EffectiveTeachingSchedule
from medsemiotics.domain.exceptions import CalendarConfigError
from medsemiotics.integrations.google_calendar.client import GoogleCalendarReader
from medsemiotics.services.calendar_config_repository import (
    CalendarConfigRepository,
)
from medsemiotics.services.calendar_filter import filter_course_calendar_events
from medsemiotics.services.effective_schedule import (
    build_effective_teaching_schedule,
)
from medsemiotics.services.schedule_repository import ScheduleRepository
from medsemiotics.services.semester_repository import SemesterRepository


class EffectiveScheduleService:
    """Read-only orchestration service for reconciling schedules and Calendar events."""

    def __init__(
        self,
        semester_repository: SemesterRepository,
        schedule_repository: ScheduleRepository,
        calendar_config_repository: CalendarConfigRepository,
        calendar_reader: GoogleCalendarReader | None = None,
    ) -> None:
        """Initialize service with domain repositories and optional Google Calendar reader."""
        self._semester_repo = semester_repository
        self._schedule_repo = schedule_repository
        self._calendar_config_repo = calendar_config_repository
        self._calendar_reader = calendar_reader

    def get_effective_schedule(
        self,
        *,
        semester_id: str,
        course_code: str,
        time_min: datetime,
        time_max: datetime,
    ) -> EffectiveTeachingSchedule:
        """Reconcile and return the EffectiveTeachingSchedule for a course.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.
            time_min: Start timestamp for calendar event querying.
            time_max: End timestamp for calendar event querying.

        Returns:
            Reconciled EffectiveTeachingSchedule instance.

        Raises:
            EffectiveScheduleError: If scopes mismatch or underlying repositories fail.
            CalendarConfigError: If calendar is enabled but no reader or calendar_id is provided.
        """
        semester = self._semester_repo.get(semester_id)
        schedule = self._schedule_repo.get(semester_id, course_code)
        calendar_config = self._calendar_config_repo.get(semester_id, course_code)

        matched_events: list[OperationalCalendarEvent] = []

        if calendar_config.enabled:
            if self._calendar_reader is None:
                msg = (
                    f"Calendar integration is enabled for {course_code} "
                    "but no GoogleCalendarReader was provided."
                )
                raise CalendarConfigError(msg)

            if not calendar_config.calendar_id:
                msg = (
                    f"Calendar integration is enabled for {course_code} but calendar_id is missing."
                )
                raise CalendarConfigError(msg)

            raw_events = self._calendar_reader.list_events(
                calendar_id=calendar_config.calendar_id,
                time_min=time_min,
                time_max=time_max,
            )
            matched_events = filter_course_calendar_events(
                raw_events,
                course_code=course_code,
                aliases=calendar_config.aliases,
            )

        return build_effective_teaching_schedule(
            semester=semester,
            schedule=schedule,
            calendar_config=calendar_config,
            calendar_events=matched_events,
        )

    def get_class_dates(
        self,
        *,
        semester_id: str,
        course_code: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[date]:
        """Convenience method returning active effective class dates."""
        effective_schedule = self.get_effective_schedule(
            semester_id=semester_id,
            course_code=course_code,
            time_min=time_min,
            time_max=time_max,
        )
        return effective_schedule.class_dates
