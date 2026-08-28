"""Domain models for teaching history and session logs."""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.topics import (
    TOPIC_ID_PATTERN,
    validate_and_normalize_topic_id,
)


class CoverageStatus(StrEnum):
    """Enumeration of pedagogical coverage states for a topic within a teaching session."""

    INTRODUCED = "introduced"
    PARTIAL = "partial"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    SKIPPED = "skipped"


def validate_and_normalize_session_id(value: object) -> str:
    """Validate and normalize a session identifier to lowercase without spaces."""
    if not isinstance(value, str):
        msg = "Session ID must be a string"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = "Session ID cannot be empty or blank"
        raise ValueError(msg)
    normalized = cleaned.lower()
    if not TOPIC_ID_PATTERN.match(normalized):
        msg = (
            f"Session ID '{normalized}' is invalid. "
            "Allowed characters: lowercase letters, numbers, underscores, hyphens without spaces."
        )
        raise ValueError(msg)
    return normalized


class TeachingSessionTopic(BaseModel):
    """Record of a topic covered in an actual teaching session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic_id: Annotated[str, Field(description="Normalized topic identifier")]
    status: Annotated[CoverageStatus, Field(description="Level of coverage achieved")]
    notes: Annotated[str | None, Field(default=None, description="Instructor notes for this topic")]

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        """Validate and normalize topic_id."""
        return validate_and_normalize_topic_id(value)

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, value: object) -> str | None:
        """Trim notes and convert empty or whitespace-only strings to None."""
        if value is None:
            return None
        if not isinstance(value, str):
            msg = "Notes must be a string or None"
            raise ValueError(msg)
        trimmed = value.strip()
        return trimmed if trimmed else None


class TeachingSession(BaseModel):
    """Immutable record of an actual classroom or clinical teaching session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: Annotated[str, Field(description="Unique normalized session identifier")]
    semester_id: Annotated[str, Field(description="Semester identifier, e.g. '2026-2'")]
    course_code: Annotated[str, Field(description="Course code, e.g. 'NEURO'")]
    session_date: Annotated[date, Field(description="Calendar date of the session")]
    sequence_number: Annotated[
        int, Field(ge=1, description="Sequential class meeting number (>= 1)")
    ]
    notes: Annotated[str | None, Field(default=None, description="General session notes")]
    topics: list[TeachingSessionTopic]

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        """Validate and normalize session_id."""
        return validate_and_normalize_session_id(value)

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

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, value: object) -> str | None:
        """Trim notes and convert empty or whitespace-only strings to None."""
        if value is None:
            return None
        if not isinstance(value, str):
            msg = "Notes must be a string or None"
            raise ValueError(msg)
        trimmed = value.strip()
        return trimmed if trimmed else None

    @model_validator(mode="after")
    def validate_session_integrity(self) -> "TeachingSession":
        """Validate that session contains topics and topic IDs are unique."""
        if not self.topics:
            msg = f"TeachingSession '{self.session_id}' must contain at least one topic."
            raise ValueError(msg)

        seen_topics: set[str] = set()
        duplicate_topics: list[str] = []
        for topic in self.topics:
            if topic.topic_id in seen_topics:
                duplicate_topics.append(topic.topic_id)
            seen_topics.add(topic.topic_id)

        if duplicate_topics:
            msg = f"Duplicate topic IDs in teaching session '{self.session_id}': {duplicate_topics}"
            raise ValueError(msg)

        return self
