"""Application service for resolving daily teaching positions from effective schedules."""

from datetime import date, datetime

from medsemiotics.domain.teaching_position import TeachingPosition
from medsemiotics.services.effective_schedule_service import (
    EffectiveScheduleService,
)
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_log_repository import TeachingLogRepository
from medsemiotics.services.teaching_position import (
    resolve_teaching_position_from_effective_schedule,
)


class EffectiveTeachingDayService:
    """Read-only service for resolving teaching positions against reconciled schedules."""

    def __init__(
        self,
        effective_schedule_service: EffectiveScheduleService,
        syllabus_repository: SyllabusRepository,
        teaching_log_repository: TeachingLogRepository,
    ) -> None:
        """Initialize service with effective schedule service and academic repositories."""
        self._effective_schedule_service = effective_schedule_service
        self._syllabus_repo = syllabus_repository
        self._teaching_log_repo = teaching_log_repository

    def get_position(
        self,
        semester_id: str,
        course_code: str,
        target_date: date,
        time_min: datetime,
        time_max: datetime,
    ) -> TeachingPosition:
        """Resolve teaching position and pacing against reconciled effective calendar.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.
            target_date: Explicit reference evaluation date.
            time_min: Start timestamp of the calendar evaluation window.
            time_max: End timestamp of the calendar evaluation window.

        Returns:
            Resolved TeachingPosition model.
        """
        effective_schedule = self._effective_schedule_service.get_effective_schedule(
            semester_id=semester_id,
            course_code=course_code,
            time_min=time_min,
            time_max=time_max,
        )
        syllabus = self._syllabus_repo.get(semester_id, course_code)
        sessions = self._teaching_log_repo.get_sessions(semester_id, course_code)

        return resolve_teaching_position_from_effective_schedule(
            target_date=target_date,
            effective_schedule=effective_schedule,
            syllabus=syllabus,
            sessions=sessions,
        )

    def get_topic_for_date(
        self,
        semester_id: str,
        course_code: str,
        target_date: date,
        time_min: datetime,
        time_max: datetime,
    ) -> str | None:
        """Get the current topic_id needing coverage on the target date.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.
            target_date: Explicit reference evaluation date.
            time_min: Start timestamp of the calendar evaluation window.
            time_max: End timestamp of the calendar evaluation window.

        Returns:
            Topic identifier string, or None if schedule is unavailable or all topics completed.
        """
        pos = self.get_position(
            semester_id=semester_id,
            course_code=course_code,
            target_date=target_date,
            time_min=time_min,
            time_max=time_max,
        )
        return pos.current_topic_id
