"""Unit tests for Syllabus domain models (SyllabusTopic, SyllabusPlan)."""

import pytest
from pydantic import ValidationError

from medsemiotics.domain.syllabus import SyllabusPlan, SyllabusTopic


class TestSyllabusDomainModel:
    """Test suite for SyllabusPlan and SyllabusTopic validation."""

    def test_valid_syllabus_plan(self) -> None:
        """Verify valid syllabus plan creation."""
        plan = SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="neuro-intro", planned_order=1, planned_week=1, required=True),
                SyllabusTopic(topic_id="mental-status", planned_order=2, planned_week=2, required=True),
            ],
        )
        assert plan.semester_id == "2026-2"
        assert plan.course_code == "NEURO"
        assert len(plan.topics) == 2

    def test_ordered_topics_returns_sorted_without_mutating_original(self) -> None:
        """Verify ordered_topics property returns sorted list without mutating the original list."""
        topic1 = SyllabusTopic(topic_id="t1", planned_order=3)
        topic2 = SyllabusTopic(topic_id="t2", planned_order=1)
        topic3 = SyllabusTopic(topic_id="t3", planned_order=2)

        plan = SyllabusPlan(
            semester_id="2026-2",
            course_code="GASTRO",
            topics=[topic1, topic2, topic3],
        )

        # Original list preserved
        assert [t.topic_id for t in plan.topics] == ["t1", "t2", "t3"]

        # Ordered property sorted
        ordered = plan.ordered_topics
        assert [t.topic_id for t in ordered] == ["t2", "t3", "t1"]
        assert [t.planned_order for t in ordered] == [1, 2, 3]

    def test_empty_topics_rejected(self) -> None:
        """Verify syllabus must contain at least one topic."""
        with pytest.raises(ValidationError, match="must contain at least one topic"):
            SyllabusPlan(
                semester_id="2026-2",
                course_code="NEURO",
                topics=[],
            )

    def test_duplicate_planned_order_rejected(self) -> None:
        """Verify duplicate planned_order values are rejected."""
        with pytest.raises(ValidationError, match="Duplicate planned_order values"):
            SyllabusPlan(
                semester_id="2026-2",
                course_code="NEURO",
                topics=[
                    SyllabusTopic(topic_id="t1", planned_order=1),
                    SyllabusTopic(topic_id="t2", planned_order=1),
                ],
            )

    def test_duplicate_topic_id_rejected(self) -> None:
        """Verify duplicate topic_id values in the same plan are rejected."""
        with pytest.raises(ValidationError, match="Duplicate topic_id values"):
            SyllabusPlan(
                semester_id="2026-2",
                course_code="NEURO",
                topics=[
                    SyllabusTopic(topic_id="neuro-intro", planned_order=1),
                    SyllabusTopic(topic_id="NEURO-INTRO", planned_order=2),  # normalizes to same
                ],
            )

    @pytest.mark.parametrize("invalid_order", [0, -1, -5])
    def test_invalid_planned_order(self, invalid_order: int) -> None:
        """Verify planned_order must be >= 1."""
        with pytest.raises(ValidationError):
            SyllabusTopic(topic_id="valid-id", planned_order=invalid_order)

    @pytest.mark.parametrize("invalid_week", [0, -1, -3])
    def test_invalid_planned_week(self, invalid_week: int) -> None:
        """Verify planned_week must be >= 1 if provided."""
        with pytest.raises(ValidationError):
            SyllabusTopic(topic_id="valid-id", planned_order=1, planned_week=invalid_week)

    def test_syllabus_immutability(self) -> None:
        """Verify SyllabusPlan is frozen."""
        plan = SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[SyllabusTopic(topic_id="neuro-intro", planned_order=1)],
        )
        with pytest.raises(ValidationError):
            plan.course_code = "GASTRO"  # type: ignore[misc]
