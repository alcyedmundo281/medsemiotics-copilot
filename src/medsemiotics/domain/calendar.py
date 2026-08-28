"""Domain models for external calendar events and course calendar configuration."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)


def _normalize_optional_text(value: object) -> str | None:
    """Trim string and normalize empty/whitespace-only values to None."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"Expected string or None, got {type(value).__name__}"
        raise ValueError(msg)
    trimmed = value.strip()
    return trimmed if trimmed else None


def _clean_string_list(value: object, field_name: str) -> list[str]:
    """Clean, trim, and deduplicate strings case-insensitively."""
    if not isinstance(value, list):
        msg = f"{field_name} must be a list of strings"
        raise ValueError(msg)

    cleaned: list[str] = []
    seen_lower: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            msg = f"{field_name} items must be strings, got {type(item).__name__}"
            raise ValueError(msg)
        trimmed = item.strip()
        if not trimmed:
            msg = f"{field_name} item must not be empty or whitespace only"
            raise ValueError(msg)

        low = trimmed.lower()
        if low in seen_lower:
            msg = f"Duplicate {field_name} found (case-insensitive): '{trimmed}'"
            raise ValueError(msg)
        seen_lower.add(low)
        cleaned.append(trimmed)

    return cleaned


class OperationalCalendarEvent(BaseModel):
    """Normalized, internal representation of an external calendar event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: Annotated[str, Field(description="Unique provider-assigned event identifier")]
    calendar_id: Annotated[str, Field(description="Identifier of the hosting calendar")]
    title: Annotated[str, Field(description="Event summary or title")]
    start: Annotated[datetime, Field(description="Timezone-aware start timestamp")]
    end: Annotated[datetime, Field(description="Timezone-aware end timestamp")]
    all_day: Annotated[bool, Field(description="True if event represents an all-day date range")]
    description: Annotated[str | None, Field(default=None, description="Optional body/description")]
    location: Annotated[str | None, Field(default=None, description="Optional physical or virtual location")]
    status: Annotated[str | None, Field(default=None, description="Optional provider status code")]
    source: Annotated[str, Field(default="google_calendar", description="Originating provider")]

    @field_validator("event_id", "calendar_id", "title", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, value: object, info: object) -> str:
        """Ensure required string fields are non-empty after trimming."""
        field_name = getattr(info, "field_name", "field")
        if not isinstance(value, str):
            msg = f"{field_name} must be a string"
            raise ValueError(msg)
        trimmed = value.strip()
        if not trimmed:
            msg = f"{field_name} must not be empty or whitespace only"
            raise ValueError(msg)
        return trimmed

    @field_validator("description", "location", "status", mode="before")
    @classmethod
    def validate_optional_strings(cls, value: object) -> str | None:
        """Trim optional strings and convert blank values to None."""
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "OperationalCalendarEvent":
        """Validate timezone awareness and timestamp ordering."""
        if self.start.tzinfo is None or self.start.tzinfo.utcoffset(self.start) is None:
            msg = f"Event '{self.event_id}' start datetime must be timezone-aware (got naive datetime)."
            raise ValueError(msg)

        if self.end.tzinfo is None or self.end.tzinfo.utcoffset(self.end) is None:
            msg = f"Event '{self.event_id}' end datetime must be timezone-aware (got naive datetime)."
            raise ValueError(msg)

        if self.start >= self.end:
            msg = f"Event '{self.event_id}' start ({self.start}) must be strictly before end ({self.end})."
            raise ValueError(msg)

        return self


class CourseCalendarConfig(BaseModel):
    """Configuration mapping a specific course to a Google Calendar and detection aliases."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Semester identifier")]
    course_code: Annotated[str, Field(description="Course code")]
    enabled: Annotated[bool, Field(default=False, description="Whether calendar integration is active")]
    calendar_id: Annotated[str | None, Field(default=None, description="Google Calendar identifier")]
    aliases: Annotated[list[str], Field(description="Title match aliases for course recognition")]
    cancellation_markers: Annotated[
        list[str],
        Field(default_factory=list, description="Keywords indicating class cancellation"),
    ]
    makeup_markers: Annotated[
        list[str],
        Field(default_factory=list, description="Keywords indicating makeup class"),
    ]

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

    @field_validator("calendar_id", mode="before")
    @classmethod
    def validate_calendar_id(cls, value: object) -> str | None:
        """Trim calendar_id and normalize empty string to None."""
        return _normalize_optional_text(value)

    @field_validator("aliases", mode="before")
    @classmethod
    def validate_aliases(cls, value: object) -> list[str]:
        """Validate, trim, and deduplicate aliases case-insensitively."""
        if not isinstance(value, list) or not value:
            msg = "aliases must be a non-empty list of strings"
            raise ValueError(msg)
        return _clean_string_list(value, "alias")

    @field_validator("cancellation_markers", "makeup_markers", mode="before")
    @classmethod
    def validate_markers(cls, value: object, info: object) -> list[str]:
        """Validate, trim, and deduplicate optional marker strings."""
        if value is None:
            return []
        field_name = getattr(info, "field_name", "marker")
        return _clean_string_list(value, field_name)

    @model_validator(mode="after")
    def validate_enabled_contract(self) -> "CourseCalendarConfig":
        """Validate that enabled calendar configurations include a non-empty calendar_id."""
        if self.enabled and not self.calendar_id:
            msg = (
                f"Course calendar config for {self.course_code} ({self.semester_id}) is enabled "
                "but calendar_id is missing or null."
            )
            raise ValueError(msg)
        return self
