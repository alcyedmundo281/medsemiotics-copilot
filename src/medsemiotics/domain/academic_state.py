"""Domain models for derived academic progress and course state."""

from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.topics import validate_and_normalize_topic_id


class TopicProgressStatus(str, Enum):
    """Enumeration of derived progression statuses for a planned syllabus topic."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class TopicProgress(BaseModel):
    """Derived academic progress metrics for an individual syllabus topic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic_id: Annotated[str, Field(description="Normalized topic identifier")]
    planned_order: Annotated[int, Field(ge=1, description="Sequence order from the syllabus")]
    required: Annotated[bool, Field(description="Whether topic is mandatory for course completion")]
    status: Annotated[TopicProgressStatus, Field(description="Derived topic progress status")]
    first_taught_date: Annotated[date | None, Field(default=None, description="Earliest teaching session date")]
    last_taught_date: Annotated[date | None, Field(default=None, description="Latest teaching session date")]
    session_count: Annotated[int, Field(default=0, ge=0, description="Total distinct teaching sessions")]

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        """Validate and normalize topic_id."""
        return validate_and_normalize_topic_id(value)

    @model_validator(mode="after")
    def validate_dates_and_counts(self) -> "TopicProgress":
        """Validate relational invariants between session_count and date fields."""
        if self.session_count == 0:
            if self.first_taught_date is not None or self.last_taught_date is not None:
                msg = (
                    f"Topic '{self.topic_id}' has session_count=0 but non-null teaching dates "
                    f"(first: {self.first_taught_date}, last: {self.last_taught_date})."
                )
                raise ValueError(msg)
        else:
            if self.first_taught_date is None or self.last_taught_date is None:
                msg = (
                    f"Topic '{self.topic_id}' has session_count={self.session_count} but missing dates "
                    f"(first: {self.first_taught_date}, last: {self.last_taught_date})."
                )
                raise ValueError(msg)
            if self.first_taught_date > self.last_taught_date:
                msg = (
                    f"Topic '{self.topic_id}' has invalid date range: "
                    f"first_taught_date ({self.first_taught_date}) > last_taught_date ({self.last_taught_date})."
                )
                raise ValueError(msg)

        return self


class CourseAcademicState(BaseModel):
    """Derived projection of academic state for an entire course and semester."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Target semester identifier")]
    course_code: Annotated[str, Field(description="Target course code")]
    topics: list[TopicProgress]

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

    @property
    def ordered_topics(self) -> list[TopicProgress]:
        """Return all topics sorted by ascending planned_order without mutating original list."""
        return sorted(self.topics, key=lambda t: t.planned_order)

    @property
    def completed_topics(self) -> list[TopicProgress]:
        """Return topics with status COMPLETED."""
        return [t for t in self.ordered_topics if t.status == TopicProgressStatus.COMPLETED]

    @property
    def in_progress_topics(self) -> list[TopicProgress]:
        """Return topics with status IN_PROGRESS."""
        return [t for t in self.ordered_topics if t.status == TopicProgressStatus.IN_PROGRESS]

    @property
    def not_started_topics(self) -> list[TopicProgress]:
        """Return topics with status NOT_STARTED."""
        return [t for t in self.ordered_topics if t.status == TopicProgressStatus.NOT_STARTED]

    @property
    def skipped_topics(self) -> list[TopicProgress]:
        """Return topics with status SKIPPED."""
        return [t for t in self.ordered_topics if t.status == TopicProgressStatus.SKIPPED]

    @property
    def required_topics(self) -> list[TopicProgress]:
        """Return topics marked as required."""
        return [t for t in self.ordered_topics if t.required]

    @property
    def completed_required_topics(self) -> list[TopicProgress]:
        """Return required topics that have achieved status COMPLETED."""
        return [t for t in self.required_topics if t.status == TopicProgressStatus.COMPLETED]

    @property
    def next_required_topic(self) -> TopicProgress | None:
        """Return the first topic in planned order that is required and not_started or in_progress.

        Skipped topics are explicitly excluded.
        """
        for topic in self.required_topics:
            if topic.status in (TopicProgressStatus.NOT_STARTED, TopicProgressStatus.IN_PROGRESS):
                return topic
        return None

    @property
    def completion_ratio(self) -> float:
        """Compute the unrounded ratio of completed required topics over total required topics (0.0 to 1.0).

        If there are no required topics, returns 1.0.
        """
        required = self.required_topics
        if not required:
            return 1.0
        return len(self.completed_required_topics) / len(required)
