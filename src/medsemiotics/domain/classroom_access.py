"""Minimal Google Classroom access contracts for the Coordination agent."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/classroom.courses.readonly"
)


class ClassroomOperation(StrEnum):
    """Classroom operations declared by the current public contract."""

    COURSE_DISCOVERY = "course_discovery"


class ClassroomDataCategory(StrEnum):
    """Data categories evaluated before a Classroom adapter may run."""

    COURSE_METADATA = "course_metadata"
    ROSTERS = "rosters"
    STUDENT_IDENTIFIERS = "student_identifiers"
    COURSEWORK = "coursework"
    SUBMISSIONS = "submissions"
    GRADES = "grades"


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


def _unique_tuple(value: object, field_name: str) -> tuple[object, ...]:
    """Require a non-empty collection without silently removing duplicate permissions."""
    if not isinstance(value, list | tuple):
        msg = f"{field_name} must be an ordered list or tuple"
        raise ValueError(msg)
    items = tuple(value)
    if not items:
        msg = f"{field_name} must contain at least one item"
        raise ValueError(msg)
    if len(items) != len(set(items)):
        msg = f"{field_name} must not contain duplicate values"
        raise ValueError(msg)
    return items


class ClassroomAccessRequest(BaseModel):
    """Auditable declaration of data and OAuth authority needed by one Classroom read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: ClassroomOperation
    data_categories: Annotated[
        tuple[ClassroomDataCategory, ...],
        Field(description="Classroom data categories the operation intends to expose"),
    ]
    oauth_scopes: Annotated[
        tuple[str, ...],
        Field(description="Exact OAuth scopes requested by the integration"),
    ]
    requested_by: str
    external_mutation: bool = False

    @field_validator("data_categories", mode="before")
    @classmethod
    def validate_data_categories(cls, value: object) -> tuple[object, ...]:
        """Require an explicit, duplicate-free data declaration."""
        return _unique_tuple(value, "data_categories")

    @field_validator("oauth_scopes", mode="before")
    @classmethod
    def validate_oauth_scopes(cls, value: object) -> tuple[str, ...]:
        """Normalize exact scopes without silently broadening or deduplicating them."""
        raw_scopes = _unique_tuple(value, "oauth_scopes")
        return tuple(_clean_required_text(scope, "oauth scope") for scope in raw_scopes)

    @field_validator("requested_by", mode="before")
    @classmethod
    def validate_requester(cls, value: object) -> str:
        """Require an accountable caller for the access audit trail."""
        return _clean_required_text(value, "requested_by")


class ClassroomAccessDecision(BaseModel):
    """Explainable result of the deterministic Classroom data-minimization policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    operation: ClassroomOperation
    approved_data_categories: tuple[ClassroomDataCategory, ...]
    approved_oauth_scopes: tuple[str, ...]
    reason: str

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        """Require every policy result to explain its outcome."""
        return _clean_required_text(value, "reason")
