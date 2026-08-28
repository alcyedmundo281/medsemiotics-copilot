"""Unit tests for academic referential validation (validate_syllabus_topics)."""

import pytest

from medsemiotics.domain.exceptions import AcademicValidationError
from medsemiotics.domain.syllabus import SyllabusPlan, SyllabusTopic
from medsemiotics.domain.topics import Topic
from medsemiotics.services.academic_validation import validate_syllabus_topics


class TestAcademicValidation:
    """Test suite for validate_syllabus_topics referential integrity checks."""

    @pytest.fixture
    def neuro_topics(self) -> list[Topic]:
        """Candidate topics fixture for NEURO."""
        return [
            Topic(topic_id="neuro-intro", course_code="NEURO", title="Introducción"),
            Topic(topic_id="mental-status", course_code="NEURO", title="Estado Mental"),
            Topic(topic_id="cranial-nerves", course_code="NEURO", title="Pares Craneales"),
        ]

    def test_all_topics_valid(self, neuro_topics: list[Topic]) -> None:
        """Verify successful validation when all syllabus topics exist and match course."""
        plan = SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="neuro-intro", planned_order=1),
                SyllabusTopic(topic_id="cranial-nerves", planned_order=2),
            ],
        )

        # Should execute cleanly without raising
        validate_syllabus_topics(plan, neuro_topics)

    def test_missing_topic_rejected(self, neuro_topics: list[Topic]) -> None:
        """Verify error raised when a syllabus references an unknown topic."""
        plan = SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="neuro-intro", planned_order=1),
                SyllabusTopic(topic_id="unknown-topic", planned_order=2),
            ],
        )

        with pytest.raises(AcademicValidationError, match="not defined in known topics"):
            validate_syllabus_topics(plan, neuro_topics)

    def test_wrong_course_topic_rejected(self, neuro_topics: list[Topic]) -> None:
        """Verify error raised when a syllabus references a topic from a different course."""
        gastro_topic = Topic(topic_id="gastro-intro", course_code="GASTRO", title="Gastro Intro")
        all_topics = [*neuro_topics, gastro_topic]

        plan = SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="neuro-intro", planned_order=1),
                SyllabusTopic(topic_id="gastro-intro", planned_order=2),
            ],
        )

        with pytest.raises(
            AcademicValidationError, match="belongs to course 'GASTRO', not 'NEURO'"
        ):
            validate_syllabus_topics(plan, all_topics)
