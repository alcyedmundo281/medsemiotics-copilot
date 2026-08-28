"""Read-only orchestration service for projecting course academic state."""

from medsemiotics.domain.academic_state import CourseAcademicState
from medsemiotics.services.academic_state import (
    build_course_academic_state,
    find_unplanned_taught_topic_ids,
)
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_log_repository import TeachingLogRepository


class CourseStateService:
    """Read-only orchestration service coordinating syllabus and teaching log repositories."""

    def __init__(
        self,
        syllabus_repository: SyllabusRepository,
        teaching_log_repository: TeachingLogRepository,
    ) -> None:
        """Initialize service with required repository instances."""
        self._syllabus_repo = syllabus_repository
        self._teaching_log_repo = teaching_log_repository

    def get_state(
        self,
        semester_id: str,
        course_code: str,
    ) -> CourseAcademicState:
        """Load syllabus and teaching logs to derive the current CourseAcademicState.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.

        Returns:
            Projected CourseAcademicState.
        """
        syllabus = self._syllabus_repo.get(semester_id, course_code)
        sessions = self._teaching_log_repo.get_sessions(semester_id, course_code)
        return build_course_academic_state(syllabus, sessions)

    def get_unplanned_taught_topic_ids(
        self,
        semester_id: str,
        course_code: str,
    ) -> list[str]:
        """Load syllabus and teaching logs to identify topics taught outside the planned syllabus.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.

        Returns:
            List of unique unplanned topic IDs ordered by first occurrence.
        """
        syllabus = self._syllabus_repo.get(semester_id, course_code)
        sessions = self._teaching_log_repo.get_sessions(semester_id, course_code)
        return find_unplanned_taught_topic_ids(syllabus, sessions)
