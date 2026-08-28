"""Domain models for syllabus planning."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.topics import validate_and_normalize_topic_id


class SyllabusTopic(BaseModel):
    """Domain model representing a topic within a planned syllabus."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic_id: Annotated[str, Field(description="Normalized topic identifier")]
    planned_order: Annotated[int, Field(ge=1, description="Sequential sequence index (>= 1)")]
    planned_week: Annotated[
        int | None,
        Field(default=None, ge=1, description="Optional target calendar week (>= 1)"),
    ]
    required: bool = True

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        """Validate and normalize topic_id."""
        return validate_and_normalize_topic_id(value)


class SyllabusPlan(BaseModel):
    """Domain model representing the intended curriculum plan for a course and semester."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Target semester identifier, e.g. '2026-2'")]
    course_code: Annotated[str, Field(description="Target course code, e.g. 'NEURO'")]
    topics: list[SyllabusTopic]

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        """Validate and normalize semester_id."""
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        """Validate and normalize course_code."""
        return validate_and_normalize_course_code(value)

    @model_validator(mode="after")
    def validate_syllabus_integrity(self) -> "SyllabusPlan":
        """Validate that syllabus has at least one topic, unique orders, and unique topic IDs."""
        if not self.topics:
            msg = f"Syllabus for {self.course_code} ({self.semester_id}) must contain at least one topic."
            raise ValueError(msg)

        seen_orders: set[int] = set()
        duplicate_orders: list[int] = []
        seen_topics: set[str] = set()
        duplicate_topics: list[str] = []

        for item in self.topics:
            if item.planned_order in seen_orders:
                duplicate_orders.append(item.planned_order)
            seen_orders.add(item.planned_order)

            if item.topic_id in seen_topics:
                duplicate_topics.append(item.topic_id)
            seen_topics.add(item.topic_id)

        if duplicate_orders:
            msg = (
                f"Duplicate planned_order values in syllabus {self.course_code} "
                f"({self.semester_id}): {duplicate_orders}"
            )
            raise ValueError(msg)

        if duplicate_topics:
            msg = (
                f"Duplicate topic_id values in syllabus {self.course_code} "
                f"({self.semester_id}): {duplicate_topics}"
            )
            raise ValueError(msg)

        return self

    @property
    def ordered_topics(self) -> list[SyllabusTopic]:
        """Return the syllabus topics sorted in ascending planned_order without mutating the input list."""
        return sorted(self.topics, key=lambda t: t.planned_order)
