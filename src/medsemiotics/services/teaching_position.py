"""Deterministic resolution service for current teaching position and pacing."""

from collections.abc import Collection
from datetime import date

from medsemiotics.domain.exceptions import AcademicStateError
from medsemiotics.domain.schedule import CourseTeachingSchedule
from medsemiotics.domain.syllabus import SyllabusPlan
from medsemiotics.domain.teaching_log import TeachingSession
from medsemiotics.domain.teaching_position import (
    TeachingPaceStatus,
    TeachingPosition,
)
from medsemiotics.services.academic_state import build_course_academic_state


def resolve_teaching_position(
    *,
    target_date: date,
    schedule: CourseTeachingSchedule,
    syllabus: SyllabusPlan,
    sessions: Collection[TeachingSession],
) -> TeachingPosition:
    """Deterministically resolve the teaching position, current topic, and pacing for a target date.

    Args:
        target_date: Explicit evaluation date.
        schedule: Institutional teaching schedule for the course.
        syllabus: Planned course curriculum syllabus.
        sessions: Complete historical teaching log sessions.

    Returns:
        TeachingPosition snapshot.

    Raises:
        AcademicStateError: If schedule, syllabus, or session scopes mismatch.
    """
    if schedule.semester_id != syllabus.semester_id or schedule.course_code != syllabus.course_code:
        msg = (
            f"Scope mismatch between schedule ({schedule.semester_id}, {schedule.course_code}) "
            f"and syllabus ({syllabus.semester_id}, {syllabus.course_code})."
        )
        raise AcademicStateError(msg)

    for session in sessions:
        if session.semester_id != syllabus.semester_id or session.course_code != syllabus.course_code:
            msg = (
                f"Scope mismatch in teaching session '{session.session_id}': "
                f"expected ({syllabus.semester_id}, {syllabus.course_code}), "
                f"got ({session.semester_id}, {session.course_code})."
            )
            raise AcademicStateError(msg)

    if not schedule.enabled:
        return TeachingPosition(
            semester_id=syllabus.semester_id,
            course_code=syllabus.course_code,
            target_date=target_date,
            is_class_date=False,
            expected_session_count=0,
            actual_session_count=0,
            expected_topic_order=None,
            current_topic_id=None,
            pace_status=TeachingPaceStatus.UNAVAILABLE,
            topic_delta=None,
        )

    is_class = schedule.is_class_date(target_date)
    expected_dates = schedule.class_dates_through(target_date)
    expected_session_count = len(expected_dates)

    # Filter strictly sessions on or before target date
    historical_sessions = [s for s in sessions if s.session_date <= target_date]
    actual_session_count = len(historical_sessions)

    # Derive academic progress through target date
    state = build_course_academic_state(syllabus, historical_sessions)
    num_planned_topics = len(syllabus.topics)

    expected_topic_order = (
        min(expected_session_count, num_planned_topics)
        if expected_session_count > 0
        else None
    )

    current_topic_id = (
        state.next_required_topic.topic_id
        if state.next_required_topic is not None
        else None
    )

    completed_required = state.completed_required_topics
    required_topics = state.required_topics
    all_completed = len(completed_required) == len(required_topics) and len(required_topics) > 0

    if expected_session_count == 0 and actual_session_count == 0:
        pace_status = TeachingPaceStatus.NOT_STARTED
        topic_delta = 0
    elif all_completed:
        pace_status = TeachingPaceStatus.COMPLETE
        actual_completed_pos = max((t.planned_order for t in completed_required), default=0)
        expected_completed_pos = (
            max(expected_topic_order - 1, 0)
            if expected_topic_order is not None
            else 0
        )
        topic_delta = actual_completed_pos - expected_completed_pos
    else:
        actual_completed_pos = max((t.planned_order for t in completed_required), default=0)
        expected_completed_pos = (
            max(expected_topic_order - 1, 0)
            if expected_topic_order is not None
            else 0
        )
        topic_delta = actual_completed_pos - expected_completed_pos

        if topic_delta > 0:
            pace_status = TeachingPaceStatus.AHEAD
        elif topic_delta == 0:
            pace_status = TeachingPaceStatus.ON_TRACK
        else:
            pace_status = TeachingPaceStatus.BEHIND

    return TeachingPosition(
        semester_id=syllabus.semester_id,
        course_code=syllabus.course_code,
        target_date=target_date,
        is_class_date=is_class,
        expected_session_count=expected_session_count,
        actual_session_count=actual_session_count,
        expected_topic_order=expected_topic_order,
        current_topic_id=current_topic_id,
        pace_status=pace_status,
        topic_delta=topic_delta,
    )
