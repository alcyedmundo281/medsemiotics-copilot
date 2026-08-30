"""Provider-neutral private course snapshot contracts.

A snapshot is private runtime state: it is never written to tracked configuration and never
published. Only `SnapshotAuditSummary` — counts, provenance, and a content fingerprint, with no
course names, identifiers, or links — is safe to log or hand to an operator.
"""

import hashlib
import json
import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class ExternalCourseProvider(StrEnum):
    """External platforms that can supply course metadata."""

    GOOGLE_CLASSROOM = "google_classroom"


class ExternalCourseLifecycle(StrEnum):
    """Provider-neutral lifecycle of an external course."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    PROVISIONED = "provisioned"
    DECLINED = "declined"
    SUSPENDED = "suspended"


def normalize_course_name(value: str) -> str:
    """Fold an external course name into a deterministic comparison form.

    Accents, case, and irregular whitespace vary between platforms and between manual edits, so
    they are removed before any later matching. The original display name is preserved separately.

    Args:
        value: Raw display name reported by the provider.

    Returns:
        Accent-free, case-folded name with collapsed whitespace.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.split()).casefold()


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


class ExternalCourse(BaseModel):
    """One external course reduced to provider-neutral, non-personal metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Annotated[ExternalCourseProvider, Field(description="Platform that reported it")]
    external_id: Annotated[str, Field(description="Opaque provider course identifier")]
    display_name: Annotated[str, Field(description="Course name as reported by the provider")]
    section: Annotated[str | None, Field(description="Optional section label")] = None
    lifecycle: Annotated[ExternalCourseLifecycle, Field(description="Normalized course state")]
    link: Annotated[str | None, Field(description="Optional HTTPS link for a human reviewer")] = (
        None
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def normalized_name(self) -> str:
        """Deterministic comparison form of the display name."""
        return normalize_course_name(self.display_name)

    @field_validator("external_id", "display_name", mode="before")
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

    @field_validator("link", mode="before")
    @classmethod
    def validate_link(cls, value: object) -> str | None:
        """Accept only an HTTPS link or no link at all."""
        cleaned = _clean_optional_text(value, "link")
        if cleaned is not None and not cleaned.startswith("https://"):
            msg = "link must be an HTTPS URL"
            raise ValueError(msg)
        return cleaned

    @field_validator("display_name")
    @classmethod
    def validate_normalizable_name(cls, value: str) -> str:
        """Reject a name that normalizes to nothing, which could never be matched later."""
        if not normalize_course_name(value):
            msg = "display_name must contain at least one comparable character"
            raise ValueError(msg)
        return value


class SnapshotAuditSummary(BaseModel):
    """The only part of a snapshot that may be logged or reported outside the process."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: ExternalCourseProvider
    captured_at: datetime
    source_reference: str
    course_count: int
    lifecycle_counts: Annotated[
        tuple[tuple[ExternalCourseLifecycle, int], ...],
        Field(description="Course counts per lifecycle, in stable lifecycle order"),
    ]
    fingerprint: Annotated[str, Field(description="Content fingerprint of the snapshot")]


class ExternalCourseSnapshot(BaseModel):
    """Private, provider-neutral point-in-time view of accessible external courses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Annotated[ExternalCourseProvider, Field(description="Platform that was read")]
    captured_at: Annotated[datetime, Field(description="Timezone-aware capture timestamp")]
    requested_by: Annotated[str, Field(description="Accountable requester of the read")]
    source_reference: Annotated[
        str, Field(description="Authorized boundary that produced the data")
    ]
    approved_scopes: Annotated[
        tuple[str, ...], Field(description="Exact authorization scopes approved for the read")
    ]
    courses: Annotated[
        tuple[ExternalCourse, ...],
        Field(description="Deterministically ordered provider-neutral courses"),
    ]

    @field_validator("requested_by", "source_reference", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require accountable provenance for every snapshot."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        """Reject naive timestamps so snapshot provenance stays unambiguous."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "captured_at must be timezone-aware"
            raise ValueError(msg)
        return value

    @field_validator("approved_scopes", mode="before")
    @classmethod
    def validate_scopes(cls, value: object) -> tuple[str, ...]:
        """Record the exact approved scopes without broadening or deduplicating them."""
        if not isinstance(value, list | tuple):
            msg = "approved_scopes must be an ordered list or tuple"
            raise ValueError(msg)
        scopes = tuple(_clean_required_text(scope, "scope") for scope in value)
        if not scopes:
            msg = "approved_scopes must contain at least one scope"
            raise ValueError(msg)
        if len(scopes) != len(set(scopes)):
            msg = "approved_scopes must not contain duplicate values"
            raise ValueError(msg)
        return scopes

    @field_validator("courses", mode="before")
    @classmethod
    def validate_courses(cls, value: object) -> tuple[ExternalCourse, ...]:
        """Reject duplicate courses and impose a deterministic, rebuildable order."""
        if not isinstance(value, list | tuple):
            msg = "courses must be an ordered list or tuple"
            raise ValueError(msg)

        courses: list[ExternalCourse] = []
        for item in value:
            if isinstance(item, ExternalCourse):
                courses.append(item)
            elif isinstance(item, dict):
                courses.append(ExternalCourse(**item))
            else:
                msg = f"course entries must be external courses, got {type(item).__name__}"
                raise ValueError(msg)

        identifiers = [(course.provider, course.external_id) for course in courses]
        if len(identifiers) != len(set(identifiers)):
            msg = "courses must not contain duplicate provider and external_id pairs"
            raise ValueError(msg)

        return tuple(
            sorted(courses, key=lambda course: (course.normalized_name, course.external_id))
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        """Content digest allowing change detection without retaining course content.

        Returns:
            Hex SHA-256 digest over the normalized course content, stable across runs.
        """
        payload = [
            [
                course.provider.value,
                course.external_id,
                course.normalized_name,
                course.section or "",
                course.lifecycle.value,
            ]
            for course in self.courses
        ]
        canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def audit_summary(self) -> SnapshotAuditSummary:
        """Build the redacted summary that may leave the process.

        Returns:
            SnapshotAuditSummary carrying provenance, counts, and the fingerprint only.
        """
        counts = {
            lifecycle: sum(1 for course in self.courses if course.lifecycle is lifecycle)
            for lifecycle in ExternalCourseLifecycle
        }
        return SnapshotAuditSummary(
            provider=self.provider,
            captured_at=self.captured_at,
            source_reference=self.source_reference,
            course_count=len(self.courses),
            lifecycle_counts=tuple(
                (lifecycle, count) for lifecycle, count in counts.items() if count
            ),
            fingerprint=self.fingerprint,
        )

    def has_same_content(self, other: "ExternalCourseSnapshot") -> bool:
        """Compare two snapshots by content, ignoring capture time and requester.

        Args:
            other: Snapshot to compare against.

        Returns:
            True when both snapshots describe the same courses from the same provider.
        """
        return self.provider is other.provider and self.fingerprint == other.fingerprint
