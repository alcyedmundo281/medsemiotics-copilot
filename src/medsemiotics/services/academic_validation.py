"""Cross-domain referential validation functions."""

from collections.abc import Collection

from medsemiotics.domain.exceptions import AcademicValidationError
from medsemiotics.domain.syllabus import SyllabusPlan
from medsemiotics.domain.topics import Topic


def validate_syllabus_topics(
    syllabus: SyllabusPlan,
    known_topics: Collection[Topic],
) -> None:
    """Validate that all topics in a SyllabusPlan exist in known_topics and match the course.

    Args:
        syllabus: The SyllabusPlan to validate.
        known_topics: Collection of Topic domain models representing the candidate topic universe.

    Raises:
        AcademicValidationError: If a syllabus topic is missing from known_topics
            or has a mismatched course_code.
    """
    topic_map: dict[str, Topic] = {topic.topic_id: topic for topic in known_topics}

    for item in syllabus.topics:
        topic = topic_map.get(item.topic_id)
        if topic is None:
            msg = (
                f"Referential integrity failure in syllabus {syllabus.course_code} "
                f"({syllabus.semester_id}): Topic '{item.topic_id}' is not defined in known topics."
            )
            raise AcademicValidationError(msg)

        if topic.course_code != syllabus.course_code:
            msg = (
                f"Referential integrity failure in syllabus {syllabus.course_code} "
                f"({syllabus.semester_id}): Topic '{item.topic_id}' belongs to course "
                f"'{topic.course_code}', not '{syllabus.course_code}'."
            )
            raise AcademicValidationError(msg)
