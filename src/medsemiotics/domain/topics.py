"""Domain models for academic topics."""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from medsemiotics.domain.academic import validate_and_normalize_course_code

TOPIC_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")

type TopicId = str


def validate_and_normalize_topic_id(value: object) -> str:
    """Validate and normalize a topic ID to lowercase with hyphens/underscores only."""
    if not isinstance(value, str):
        msg = "Topic ID must be a string"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = "Topic ID cannot be empty or blank"
        raise ValueError(msg)
    normalized = cleaned.lower()
    if not TOPIC_ID_PATTERN.match(normalized):
        msg = (
            f"Topic ID '{normalized}' is invalid. "
            "Allowed characters are lowercase letters, numbers, underscores, and hyphens without spaces."
        )
        raise ValueError(msg)
    return normalized


class Topic(BaseModel):
    """Domain model representing a discrete academic topic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic_id: Annotated[str, Field(description="Unique normalized topic identifier, e.g. 'neuro-intro'")]
    course_code: Annotated[str, Field(description="Course code to which this topic belongs, e.g. 'NEURO'")]
    title: Annotated[str, Field(description="Human-readable topic title")]
    description: Annotated[str | None, Field(default=None, description="Optional topic description")]
    active: bool = True

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        """Validate and normalize topic_id."""
        return validate_and_normalize_topic_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        """Validate and normalize course_code."""
        return validate_and_normalize_course_code(value)

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        """Validate and trim title."""
        if not isinstance(value, str):
            msg = "Title must be a string"
            raise ValueError(msg)
        trimmed = value.strip()
        if not trimmed:
            msg = "Title cannot be empty or blank"
            raise ValueError(msg)
        return trimmed

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> str | None:
        """Trim description and convert empty or whitespace-only strings to None."""
        if value is None:
            return None
        if not isinstance(value, str):
            msg = "Description must be a string or None"
            raise ValueError(msg)
        trimmed = value.strip()
        return trimmed if trimmed else None
