"""Application service for resolving daily teaching positions and topics for target dates."""

from datetime import date

from medsemiotics.domain.teaching_position import TeachingPosition
from medsemiotics.services.schedule_repository import ScheduleRepository
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_log_repository import TeachingLogRepository
from medsemiotics.services.teaching_position import resolve_teaching_position


class TeachingDayService:
    """Read-only orchestration service for evaluating teaching schedules and current topics."""

    def __init__(
        self,
        schedule_repository: ScheduleRepository,
        syllabus_repository: SyllabusRepository,
        teaching_log_repository: TeachingLogRepository,
    ) -> None:
        """Initialize service with required repositories."""
        self._schedule_repo = schedule_repository
        self._syllabus_repo = syllabus_repository
        self._teaching_log_repo = teaching_log_repository

    def get_position(
        self,
        semester_id: str,
        course_code: str,
        target_date: date,
    ) -> TeachingPosition:
        """Retrieve repositories data and resolve teaching position for a specific target date.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.
            target_date: Explicit evaluation date.

        Returns:
            Resolved TeachingPosition model.
        """
        schedule = self._schedule_repo.get(semester_id, course_code)
        syllabus = self._syllabus_repo.get(semester_id, course_code)
        sessions = self._teaching_log_repo.get_sessions(semester_id, course_code)

        return resolve_teaching_position(
            target_date=target_date,
            schedule=schedule,
            syllabus=syllabus,
            sessions=sessions,
        )

    def get_topic_for_date(
        self,
        semester_id: str,
        course_code: str,
        target_date: date,
    ) -> str | None:
        """Get the current topic_id needing coverage on the target date.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.
            target_date: Explicit evaluation date.

        Returns:
            Current topic_id string, or None if schedule is disabled or all topics are completed.
        """
        position = self.get_position(semester_id, course_code, target_date)
        return position.current_topic_id
