"""Domain models for coaching briefing, calendar publishing requests, and publishing results."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)


class CalendarPublishAction(StrEnum):
    """Action performed when publishing a calendar event."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


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
    """Clean and trim a list of strings, rejecting blank/empty items."""
    if value is None:
        return []
    if not isinstance(value, list):
        msg = f"{field_name} must be a list of strings, got {type(value).__name__}"
        raise ValueError(msg)

    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            msg = f"{field_name} items must be strings, got {type(item).__name__}"
            raise ValueError(msg)
        trimmed = item.strip()
        if not trimmed:
            msg = f"{field_name} items must not be empty or whitespace only"
            raise ValueError(msg)
        cleaned.append(trimmed)

    return cleaned


def _validate_url(value: object) -> str | None:
    """Validate that a string is a valid HTTP/HTTPS URL."""
    cleaned = _normalize_optional_text(value)
    if cleaned is None:
        return None

    try:
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            msg = f"Invalid URL '{cleaned}'. Must be an http or https URL with a valid host."
            raise ValueError(msg)
    except Exception as err:
        if isinstance(err, ValueError):
            raise
        msg = f"Invalid URL '{cleaned}': {err}"
        raise ValueError(msg) from err

    return cleaned


class CoachingBrief(BaseModel):
    """Structured pedagogical briefing for an upcoming teaching session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Semester identifier")]
    course_code: Annotated[str, Field(description="Course code")]
    class_date: Annotated[date, Field(description="Target date of the teaching session")]
    topic_id: Annotated[str | None, Field(default=None, description="Optional topic identifier")]
    topic_title: Annotated[str, Field(description="Human-readable title of the topic")]
    learning_objectives: Annotated[
        list[str],
        Field(default_factory=list, description="Core learning objectives for students"),
    ]
    coaching_tips: Annotated[
        list[str],
        Field(default_factory=list, description="Pedagogical tips and emphasis points"),
    ]
    teaching_questions: Annotated[
        list[str],
        Field(default_factory=list, description="Trigger questions for classroom discussion"),
    ]
    common_pitfalls: Annotated[
        list[str],
        Field(default_factory=list, description="Frequent student misconceptions"),
    ]
    material_notes: Annotated[
        list[str],
        Field(
            default_factory=list, description="Required equipment, slides, or clinical materials"
        ),
    ]
    assignment_note: Annotated[
        str | None,
        Field(default=None, description="Brief note on pending or assigned homework/tasks"),
    ]
    powersemiotics_url: Annotated[
        str | None,
        Field(default=None, description="Link to supplementary PowerSemiotics digital resource"),
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

    @field_validator("topic_id", "assignment_note", mode="before")
    @classmethod
    def validate_optional_strings(cls, value: object) -> str | None:
        """Trim optional strings and convert blank values to None."""
        return _normalize_optional_text(value)

    @field_validator("topic_title", mode="before")
    @classmethod
    def validate_topic_title(cls, value: object) -> str:
        """Ensure topic_title is non-empty after trimming."""
        if not isinstance(value, str):
            msg = f"topic_title must be a string, got {type(value).__name__}"
            raise ValueError(msg)
        trimmed = value.strip()
        if not trimmed:
            msg = "topic_title must not be empty or whitespace only"
            raise ValueError(msg)
        return trimmed

    @field_validator(
        "learning_objectives",
        "coaching_tips",
        "teaching_questions",
        "common_pitfalls",
        "material_notes",
        mode="before",
    )
    @classmethod
    def validate_list_fields(cls, value: object, info: object) -> list[str]:
        """Clean and validate list fields."""
        field_name = getattr(info, "field_name", "list field")
        return _clean_string_list(value, field_name)

    @field_validator("powersemiotics_url", mode="before")
    @classmethod
    def validate_powersemiotics_url(cls, value: object) -> str | None:
        """Validate powersemiotics_url is a valid HTTP/HTTPS URL."""
        return _validate_url(value)


class CalendarPublishRequest(BaseModel):
    """Provider-neutral request to publish or update an owned calendar event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calendar_id: Annotated[str, Field(description="Google Calendar identifier")]
    event_date: Annotated[date, Field(description="Academic local date of the event")]
    start: Annotated[datetime, Field(description="Timezone-aware start timestamp")]
    end: Annotated[datetime, Field(description="Timezone-aware end timestamp")]
    title: Annotated[str, Field(description="Event title / summary")]
    description: Annotated[str, Field(description="Formatted event body description")]
    location: Annotated[
        str | None, Field(default=None, description="Optional physical or virtual location")
    ]
    reminders_minutes: Annotated[
        list[int],
        Field(default_factory=list, description="Popup reminder lead times in minutes"),
    ]
    metadata: Annotated[
        dict[str, str], Field(description="MedSemiotics ownership extended properties")
    ]

    @field_validator("calendar_id", "title", mode="before")
    @classmethod
    def validate_non_empty_strings(cls, value: object, info: object) -> str:
        """Ensure required string fields are non-empty after trimming."""
        field_name = getattr(info, "field_name", "field")
        if not isinstance(value, str):
            msg = f"{field_name} must be a string, got {type(value).__name__}"
            raise ValueError(msg)
        trimmed = value.strip()
        if not trimmed:
            msg = f"{field_name} must not be empty or whitespace only"
            raise ValueError(msg)
        return trimmed

    @field_validator("location", mode="before")
    @classmethod
    def validate_location(cls, value: object) -> str | None:
        """Trim location and convert blank string to None."""
        return _normalize_optional_text(value)

    @field_validator("reminders_minutes", mode="before")
    @classmethod
    def validate_reminders(cls, value: object) -> list[int]:
        """Validate and deduplicate reminder minutes in ascending order."""
        if value is None:
            return []
        if not isinstance(value, (list, set, tuple)):
            msg = f"reminders_minutes must be a collection of integers, got {type(value).__name__}"
            raise ValueError(msg)

        cleaned_reminders: set[int] = set()
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool):
                msg = f"Reminder minute value must be an integer, got {type(item).__name__}"
                raise ValueError(msg)
            if item <= 0:
                msg = f"Reminder minute must be a positive integer, got {item}"
                raise ValueError(msg)
            if item > 40320:  # Max 4 weeks
                msg = (
                    "Reminder minute exceeds supported maximum "
                    f"(40320 minutes / 4 weeks), got {item}"
                )
                raise ValueError(msg)
            cleaned_reminders.add(item)

        return sorted(cleaned_reminders)

    @model_validator(mode="after")
    def validate_timestamps_and_date(self) -> "CalendarPublishRequest":
        """Validate timezone awareness, timestamp ordering, and date alignment."""
        if self.start.tzinfo is None or self.start.tzinfo.utcoffset(self.start) is None:
            msg = f"start datetime must be timezone-aware (got {self.start})."
            raise ValueError(msg)

        if self.end.tzinfo is None or self.end.tzinfo.utcoffset(self.end) is None:
            msg = f"end datetime must be timezone-aware (got {self.end})."
            raise ValueError(msg)

        if self.start >= self.end:
            msg = f"start ({self.start}) must be strictly before end ({self.end})."
            raise ValueError(msg)

        if self.event_date != self.start.date():
            msg = (
                f"event_date ({self.event_date}) does not match "
                f"start timestamp date ({self.start.date()})."
            )
            raise ValueError(msg)

        return self


class CalendarPublishResult(BaseModel):
    """Outcome of a calendar publish operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calendar_id: Annotated[str, Field(description="Google Calendar identifier")]
    event_id: Annotated[str, Field(description="Google Calendar event identifier")]
    action: Annotated[CalendarPublishAction, Field(description="Action performed")]


class ManagedCalendarEvent(BaseModel):
    """Internal model representing an existing MedSemiotics-owned calendar event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calendar_id: Annotated[str, Field(description="Google Calendar identifier")]
    event_id: Annotated[str, Field(description="Google Calendar event identifier")]
    title: Annotated[str, Field(description="Event title")]
    description: Annotated[str, Field(description="Event description body")]
    start: Annotated[datetime, Field(description="Timezone-aware start timestamp")]
    end: Annotated[datetime, Field(description="Timezone-aware end timestamp")]
    location: Annotated[str | None, Field(default=None, description="Event location")]
    reminders_minutes: Annotated[
        list[int], Field(default_factory=list, description="Configured reminder minutes")
    ]
    metadata: Annotated[
        dict[str, str], Field(default_factory=dict, description="Private extended properties")
    ]
