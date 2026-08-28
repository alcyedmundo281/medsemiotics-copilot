"""Domain layer: KNOW.

Contains domain data models, entities, and state definitions.
"""

from medsemiotics.domain.academic import (
    Course,
    CourseCode,
    SemesterConfig,
    SemesterId,
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.academic_state import (
    CourseAcademicState,
    TopicProgress,
    TopicProgressStatus,
)
from medsemiotics.domain.exceptions import (
    AcademicStateError,
    AcademicValidationError,
    MedSemioticsError,
    ScheduleError,
    ScheduleNotFoundError,
    ScheduleValidationError,
    SemesterConfigError,
    SemesterConfigNotFoundError,
    SemesterConfigValidationError,
    SyllabusError,
    SyllabusNotFoundError,
    SyllabusValidationError,
    TeachingLogError,
    TeachingLogNotFoundError,
    TeachingLogValidationError,
)
from medsemiotics.domain.schedule import (
    ClassMeetingRule,
    ClassWeekday,
    CourseTeachingSchedule,
    ScheduleException,
    ScheduleExceptionType,
)
from medsemiotics.domain.syllabus import SyllabusPlan, SyllabusTopic
from medsemiotics.domain.teaching_log import (
    CoverageStatus,
    TeachingSession,
    TeachingSessionTopic,
    validate_and_normalize_session_id,
)
from medsemiotics.domain.teaching_position import (
    TeachingPaceStatus,
    TeachingPosition,
)
from medsemiotics.domain.topics import Topic, TopicId, validate_and_normalize_topic_id

__all__ = [
    "AcademicStateError",
    "AcademicValidationError",
    "ClassMeetingRule",
    "ClassWeekday",
    "Course",
    "CourseAcademicState",
    "CourseCode",
    "CourseTeachingSchedule",
    "CoverageStatus",
    "MedSemioticsError",
    "ScheduleError",
    "ScheduleException",
    "ScheduleExceptionType",
    "ScheduleNotFoundError",
    "ScheduleValidationError",
    "SemesterConfig",
    "SemesterConfigError",
    "SemesterConfigNotFoundError",
    "SemesterConfigValidationError",
    "SemesterId",
    "SyllabusError",
    "SyllabusNotFoundError",
    "SyllabusPlan",
    "SyllabusTopic",
    "SyllabusValidationError",
    "TeachingLogError",
    "TeachingLogNotFoundError",
    "TeachingLogValidationError",
    "TeachingPaceStatus",
    "TeachingPosition",
    "TeachingSession",
    "TeachingSessionTopic",
    "Topic",
    "TopicId",
    "TopicProgress",
    "TopicProgressStatus",
    "validate_and_normalize_course_code",
    "validate_and_normalize_semester_id",
    "validate_and_normalize_session_id",
    "validate_and_normalize_topic_id",
]
