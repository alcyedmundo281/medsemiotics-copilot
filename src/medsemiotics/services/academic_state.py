"""Pure deterministic projection functions for deriving academic course state."""

from collections.abc import Collection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

from medsemiotics.domain.academic_state import (
    CourseAcademicState,
    TopicProgress,
    TopicProgressStatus,
)
from medsemiotics.domain.exceptions import AcademicStateError
from medsemiotics.domain.syllabus import SyllabusPlan
from medsemiotics.domain.teaching_log import CoverageStatus, TeachingSession


def _validate_session_scope(
    syllabus: SyllabusPlan,
    sessions: Collection[TeachingSession],
) -> None:
    """Validate that every session belongs to the syllabus semester and course.

    Raises:
        AcademicStateError: If any session's semester_id or course_code does not match the syllabus.
    """
    for session in sessions:
        if session.semester_id != syllabus.semester_id:
            msg = (
                f"Scope mismatch in teaching session '{session.session_id}': "
                f"expected semester '{syllabus.semester_id}', got '{session.semester_id}'."
            )
            raise AcademicStateError(msg)

        if session.course_code != syllabus.course_code:
            msg = (
                f"Scope mismatch in teaching session '{session.session_id}': "
                f"expected course '{syllabus.course_code}', got '{session.course_code}'."
            )
            raise AcademicStateError(msg)


def _sort_sessions_chronologically(
    sessions: Collection[TeachingSession],
) -> list[TeachingSession]:
    """Sort teaching sessions deterministically by session_date, sequence_number, and session_id."""
    return sorted(
        sessions,
        key=lambda s: (s.session_date, s.sequence_number, s.session_id),
    )


def build_course_academic_state(
    syllabus: SyllabusPlan,
    sessions: Collection[TeachingSession],
) -> CourseAcademicState:
    """Derive deterministic CourseAcademicState from a SyllabusPlan and historical TeachingSessions.

    Args:
        syllabus: The target course syllabus plan.
        sessions: Historical teaching sessions for this course and semester.

    Returns:
        CourseAcademicState containing progress projections for all syllabus topics.

    Raises:
        AcademicStateError: If any session does not match syllabus semester or course scope.
    """
    _validate_session_scope(syllabus, sessions)
    sorted_sessions = _sort_sessions_chronologically(sessions)

    topics_progress: list[TopicProgress] = []

    for planned_topic in syllabus.topics:
        target_id = planned_topic.topic_id
        current_status = TopicProgressStatus.NOT_STARTED
        session_count = 0
        first_date: date | None = None
        last_date: date | None = None

        for session in sorted_sessions:
            # Find if this session touched the topic
            matching_session_topic = next(
                (st for st in session.topics if st.topic_id == target_id),
                None,
            )

            if matching_session_topic is not None:
                session_count += 1
                if first_date is None:
                    first_date = session.session_date
                last_date = session.session_date

                # State transition logic
                if current_status == TopicProgressStatus.COMPLETED:
                    # Completed is terminal for projection purposes
                    continue

                event_status = matching_session_topic.status
                if event_status in (CoverageStatus.INTRODUCED, CoverageStatus.PARTIAL):
                    current_status = TopicProgressStatus.IN_PROGRESS
                elif event_status == CoverageStatus.COMPLETED:
                    current_status = TopicProgressStatus.COMPLETED
                elif event_status == CoverageStatus.SKIPPED:
                    current_status = TopicProgressStatus.SKIPPED
                elif event_status == CoverageStatus.REVIEWED:
                    if current_status == TopicProgressStatus.SKIPPED:
                        # Skipped remains skipped on reviewed
                        pass
                    else:
                        current_status = TopicProgressStatus.IN_PROGRESS

        topics_progress.append(
            TopicProgress(
                topic_id=planned_topic.topic_id,
                planned_order=planned_topic.planned_order,
                required=planned_topic.required,
                status=current_status,
                first_taught_date=first_date,
                last_taught_date=last_date,
                session_count=session_count,
            )
        )

    return CourseAcademicState(
        semester_id=syllabus.semester_id,
        course_code=syllabus.course_code,
        topics=topics_progress,
    )


def find_unplanned_taught_topic_ids(
    syllabus: SyllabusPlan,
    sessions: Collection[TeachingSession],
) -> list[str]:
    """Find unique topic IDs that appear in teaching history but are not part of the syllabus.

    Args:
        syllabus: The target course syllabus plan.
        sessions: Historical teaching sessions for this course and semester.

    Returns:
        List of unique topic IDs ordered deterministically by first historical appearance.

    Raises:
        AcademicStateError: If any session does not match syllabus semester or course scope.
    """
    _validate_session_scope(syllabus, sessions)
    sorted_sessions = _sort_sessions_chronologically(sessions)

    planned_topic_ids = {t.topic_id for t in syllabus.topics}
    unplanned_topic_ids: list[str] = []
    seen_unplanned: set[str] = set()

    for session in sorted_sessions:
        for session_topic in session.topics:
            topic_id = session_topic.topic_id
            if topic_id not in planned_topic_ids and topic_id not in seen_unplanned:
                seen_unplanned.add(topic_id)
                unplanned_topic_ids.append(topic_id)

    return unplanned_topic_ids
