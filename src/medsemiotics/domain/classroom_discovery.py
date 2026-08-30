"""Sanitized, metadata-only Google Classroom course discovery contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClassroomCourseState(StrEnum):
    """Course lifecycle states exposed by metadata-only discovery."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    PROVISIONED = "provisioned"
    DECLINED = "declined"
    SUSPENDED = "suspended"


def _clean_required_text(value: object, field_name: str) -> str:
    """Normalize a required string and reject blank values."""
    if not isinstance(value, str):
        msg = f"{field_name} must be a string, got {type(value).__name__}"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = f"{field_name} must not be empty or whitespace only"
        raise ValueError(msg)
    return cleaned


def _clean_optional_text(value: object, field_name: str) -> str | None:
    """Normalize an optional string, treating blank input as absent metadata."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"{field_name} must be a string or null, got {type(value).__name__}"
        raise ValueError(msg)
    cleaned = value.strip()
    return cleaned or None


class DiscoveredClassroomCourse(BaseModel):
    """One accessible Classroom course reduced to non-personal course metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    course_id: Annotated[str, Field(description="Opaque Classroom course identifier")]
    name: Annotated[str, Field(description="Course display name")]
    section: Annotated[str | None, Field(description="Optional course section label")] = None
    course_state: Annotated[
        ClassroomCourseState, Field(description="Course lifecycle state reported by Classroom")
    ]
    alternate_link: Annotated[
        str | None, Field(description="Optional HTTPS Classroom link for a human reviewer")
    ] = None

    @field_validator("course_id", "name", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require identifying metadata to be present and non-blank."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("section", mode="before")
    @classmethod
    def validate_section(cls, value: object) -> str | None:
        """Normalize the optional section label."""
        return _clean_optional_text(value, "section")

    @field_validator("alternate_link", mode="before")
    @classmethod
    def validate_alternate_link(cls, value: object) -> str | None:
        """Accept only an HTTPS Classroom link or no link at all."""
        cleaned = _clean_optional_text(value, "alternate_link")
        if cleaned is not None and not cleaned.startswith("https://"):
            msg = "alternate_link must be an HTTPS URL"
            raise ValueError(msg)
        return cleaned


class ClassroomCourseDiscovery(BaseModel):
    """Auditable result of one metadata-only course discovery read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_by: Annotated[str, Field(description="Accountable requester of the read")]
    retrieved_at: Annotated[datetime, Field(description="Timezone-aware read timestamp")]
    source_deployment_id: Annotated[
        str, Field(description="Apps Script deployment that performed the authorized read")
    ]
    approved_oauth_scopes: Annotated[
        tuple[str, ...], Field(description="Exact OAuth scopes approved for this read")
    ]
    courses: Annotated[
        tuple[DiscoveredClassroomCourse, ...],
        Field(description="Deterministically ordered, sanitized course metadata"),
    ]

    @field_validator("requested_by", "source_deployment_id", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require accountable provenance for every discovery result."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("retrieved_at")
    @classmethod
    def validate_retrieved_at(cls, value: datetime) -> datetime:
        """Reject naive timestamps so audit evidence stays unambiguous."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "retrieved_at must be timezone-aware"
            raise ValueError(msg)
        return value

    @field_validator("approved_oauth_scopes", mode="before")
    @classmethod
    def validate_scopes(cls, value: object) -> tuple[str, ...]:
        """Record the exact approved scopes without broadening or deduplicating them."""
        if not isinstance(value, list | tuple):
            msg = "approved_oauth_scopes must be an ordered list or tuple"
            raise ValueError(msg)
        scopes = tuple(_clean_required_text(scope, "oauth scope") for scope in value)
        if not scopes:
            msg = "approved_oauth_scopes must contain at least one scope"
            raise ValueError(msg)
        if len(scopes) != len(set(scopes)):
            msg = "approved_oauth_scopes must not contain duplicate values"
            raise ValueError(msg)
        return scopes

    @field_validator("courses", mode="before")
    @classmethod
    def validate_courses(cls, value: object) -> tuple[DiscoveredClassroomCourse, ...]:
        """Reject duplicate courses and impose a deterministic, rebuildable order."""
        if not isinstance(value, list | tuple):
            msg = "courses must be an ordered list or tuple"
            raise ValueError(msg)

        courses: list[DiscoveredClassroomCourse] = []
        for item in value:
            if isinstance(item, DiscoveredClassroomCourse):
                courses.append(item)
            elif isinstance(item, dict):
                courses.append(DiscoveredClassroomCourse(**item))
            else:
                msg = f"course entries must be course metadata, got {type(item).__name__}"
                raise ValueError(msg)

        identifiers = [course.course_id for course in courses]
        if len(identifiers) != len(set(identifiers)):
            msg = "courses must not contain duplicate course_id values"
            raise ValueError(msg)

        return tuple(sorted(courses, key=lambda course: (course.name.casefold(), course.course_id)))
