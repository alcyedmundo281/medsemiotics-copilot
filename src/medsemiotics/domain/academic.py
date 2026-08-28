"""Academic domain models for courses and semester configurations."""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SEMESTER_ID_PATTERN = re.compile(r"^\d{4}-[12]$")
COURSE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

type CourseCode = str
type SemesterId = str


def validate_and_normalize_course_code(value: object) -> str:
    """Validate and normalize a course code to uppercase without whitespace."""
    if not isinstance(value, str):
        msg = "Course code must be a string"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = "Course code cannot be empty or blank"
        raise ValueError(msg)
    normalized = cleaned.upper()
    if not COURSE_CODE_PATTERN.match(normalized):
        msg = (
            f"Course code '{normalized}' is invalid. "
            "Allowed characters are letters, numbers, underscores, and hyphens."
        )
        raise ValueError(msg)
    return normalized


def validate_and_normalize_semester_id(value: object) -> str:
    """Validate and normalize a semester ID adhering to YYYY-1 or YYYY-2 format."""
    if not isinstance(value, str):
        msg = "Semester ID must be a string"
        raise ValueError(msg)
    cleaned = value.strip()
    if not SEMESTER_ID_PATTERN.match(cleaned):
        msg = f"Invalid semester_id '{cleaned}'. Must match format YYYY-1 or YYYY-2."
        raise ValueError(msg)
    return cleaned


class Course(BaseModel):
    """Domain model representing an academic course."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Annotated[str, Field(description="Normalized course identifier")]
    name: Annotated[str, Field(description="Human-readable course title")]
    active: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def validate_and_normalize_code(cls, value: object) -> str:
        """Validate and normalize course code."""
        return validate_and_normalize_course_code(value)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        """Validate and trim course name."""
        if not isinstance(value, str):
            msg = "Course name must be a string"
            raise ValueError(msg)
        trimmed = value.strip()
        if not trimmed:
            msg = "Course name cannot be empty or blank"
            raise ValueError(msg)
        return trimmed


class SemesterConfig(BaseModel):
    """Domain model representing a semester configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Unique semester identifier, e.g. 2026-2")]
    display_name: Annotated[str, Field(description="Display label for the semester")]
    active: bool
    courses: list[Course]

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_and_normalize_semester_id(cls, value: object) -> str:
        """Validate that semester_id conforms to the YYYY-1 or YYYY-2 format."""
        return validate_and_normalize_semester_id(value)

    @field_validator("display_name", mode="before")
    @classmethod
    def validate_display_name(cls, value: object) -> str:
        """Validate and trim display_name."""
        if not isinstance(value, str):
            msg = "Display name must be a string"
            raise ValueError(msg)
        trimmed = value.strip()
        if not trimmed:
            msg = "Display name cannot be empty or blank"
            raise ValueError(msg)
        return trimmed

    @model_validator(mode="after")
    def validate_semester_integrity(self) -> "SemesterConfig":
        """Ensure the semester has at least one course and all course codes are unique."""
        if not self.courses:
            msg = "SemesterConfig must contain at least one course."
            raise ValueError(msg)

        seen_codes: set[str] = set()
        duplicates: list[str] = []
        for course in self.courses:
            if course.code in seen_codes:
                duplicates.append(course.code)
            seen_codes.add(course.code)

        if duplicates:
            msg = f"Duplicate course codes detected in semester '{self.semester_id}': {duplicates}"
            raise ValueError(msg)

        return self
