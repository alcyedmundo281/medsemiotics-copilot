"""Read-only coordination view across Classroom, Calendar, syllabus, and teaching state."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.external_courses import ExternalCourseLifecycle


class ClassroomLinkStatus(StrEnum):
    """Outcome of matching a tracked course to an external Classroom course."""

    LINKED = "linked"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    NOT_READ = "not_read"


class CalendarLinkStatus(StrEnum):
    """Configured state of a course's Google Calendar binding."""

    CONFIGURED = "configured"
    DISABLED = "disabled"
    MISSING = "missing"


class CoordinationReadiness(StrEnum):
    """Whether a course is fully wired for coordinated teaching support."""

    READY = "ready"
    PARTIAL = "partial"
    BLOCKED = "blocked"


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


class ClassroomLink(BaseModel):
    """Explainable result of binding one tracked course to Classroom course metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ClassroomLinkStatus
    external_id: Annotated[str | None, Field(description="Linked external course id")] = None
    display_name: Annotated[str | None, Field(description="Linked course display name")] = None
    lifecycle: Annotated[
        ExternalCourseLifecycle | None, Field(description="Lifecycle of the linked course")
    ] = None
    candidate_ids: Annotated[
        tuple[str, ...],
        Field(description="External ids considered when the match was not decisive"),
    ] = ()
    reason: Annotated[str, Field(description="Why this outcome was reached")]

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        """Require every binding outcome to explain itself."""
        return _clean_required_text(value, "reason")

    @model_validator(mode="after")
    def validate_link_evidence(self) -> "ClassroomLink":
        """A link is either decisive with course metadata, or carries none of it."""
        if self.status is ClassroomLinkStatus.LINKED:
            if self.external_id is None or self.display_name is None or self.lifecycle is None:
                msg = "A linked course requires external_id, display_name, and lifecycle"
                raise ValueError(msg)
            if self.candidate_ids:
                msg = "A linked course must not carry unresolved candidates"
                raise ValueError(msg)
            return self

        if self.external_id is not None or self.display_name is not None:
            msg = f"Status '{self.status.value}' must not carry linked course metadata"
            raise ValueError(msg)
        if self.lifecycle is not None:
            msg = f"Status '{self.status.value}' must not carry a course lifecycle"
            raise ValueError(msg)
        if self.status is ClassroomLinkStatus.AMBIGUOUS and not self.candidate_ids:
            msg = "An ambiguous match must list the candidate ids it could not decide between"
            raise ValueError(msg)
        return self


class CalendarLink(BaseModel):
    """Configured Calendar binding for one tracked course."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: CalendarLinkStatus
    calendar_id: Annotated[str | None, Field(description="Bound calendar identifier")] = None
    reason: Annotated[str, Field(description="Why this outcome was reached")]

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        """Require every binding outcome to explain itself."""
        return _clean_required_text(value, "reason")

    @model_validator(mode="after")
    def validate_calendar_evidence(self) -> "CalendarLink":
        """Only a configured binding may name a calendar."""
        if self.status is CalendarLinkStatus.CONFIGURED and self.calendar_id is None:
            msg = "A configured calendar binding requires calendar_id"
            raise ValueError(msg)
        if self.status is CalendarLinkStatus.MISSING and self.calendar_id is not None:
            msg = "A missing calendar binding must not name a calendar"
            raise ValueError(msg)
        return self


class AcademicProgressSummary(BaseModel):
    """Counts derived from tracked syllabus and teaching-log state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_topics: Annotated[int, Field(ge=0, description="Planned topics in the syllabus")]
    completed_topics: Annotated[int, Field(ge=0, description="Topics recorded as completed")]
    in_progress_topics: Annotated[int, Field(ge=0, description="Topics partially covered")]
    not_started_topics: Annotated[int, Field(ge=0, description="Topics never taught")]
    skipped_topics: Annotated[int, Field(ge=0, description="Topics explicitly skipped")]
    next_required_topic_id: Annotated[
        str | None, Field(description="Next required topic in planned order")
    ] = None

    @model_validator(mode="after")
    def validate_topic_totals(self) -> "AcademicProgressSummary":
        """Every counted topic must belong to exactly one status bucket."""
        counted = (
            self.completed_topics
            + self.in_progress_topics
            + self.not_started_topics
            + self.skipped_topics
        )
        if counted != self.total_topics:
            msg = f"Topic status counts ({counted}) must sum to total_topics ({self.total_topics})"
            raise ValueError(msg)
        return self


class UnmatchedExternalCourse(BaseModel):
    """An accessible external course that no tracked course claims."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    external_id: Annotated[str, Field(description="Opaque provider course identifier")]
    display_name: Annotated[str, Field(description="Course name as reported by the provider")]
    lifecycle: Annotated[ExternalCourseLifecycle, Field(description="Normalized course state")]


class CourseCoordinationEntry(BaseModel):
    """How one tracked course is wired across Classroom, Calendar, and academic state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    course_code: Annotated[str, Field(description="Tracked course code")]
    course_name: Annotated[str, Field(description="Tracked course name")]
    classroom: ClassroomLink
    calendar: CalendarLink
    academic: AcademicProgressSummary
    readiness: CoordinationReadiness
    blockers: Annotated[
        tuple[str, ...], Field(description="Human-readable gaps preventing full coordination")
    ] = ()

    @field_validator("course_code", "course_name", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require identifying course fields."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @model_validator(mode="after")
    def validate_readiness_evidence(self) -> "CourseCoordinationEntry":
        """Readiness must agree with the recorded blockers."""
        if self.readiness is CoordinationReadiness.READY and self.blockers:
            msg = "A ready course must not list blockers"
            raise ValueError(msg)
        if self.readiness is not CoordinationReadiness.READY and not self.blockers:
            msg = f"Readiness '{self.readiness.value}' requires at least one blocker"
            raise ValueError(msg)
        return self


class CoordinationView(BaseModel):
    """Point-in-time read-only coordination view for one semester."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Semester the view describes")]
    generated_at: Annotated[datetime, Field(description="Timezone-aware generation timestamp")]
    requested_by: Annotated[str, Field(description="Accountable requester of the view")]
    entries: Annotated[
        tuple[CourseCoordinationEntry, ...],
        Field(description="Active courses ordered by course code"),
    ]
    unmatched_external_courses: Annotated[
        tuple[UnmatchedExternalCourse, ...],
        Field(description="Accessible external courses no tracked course claims"),
    ] = ()
    inactive_course_codes: Annotated[
        tuple[str, ...], Field(description="Tracked courses excluded because they are inactive")
    ] = ()

    @field_validator("semester_id", "requested_by", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require accountable provenance for every view."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at(cls, value: datetime) -> datetime:
        """Reject naive timestamps so the view's provenance stays unambiguous."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "generated_at must be timezone-aware"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_entry_order(self) -> "CoordinationView":
        """Entries must be unique and ordered so the view is rebuildable."""
        codes = [entry.course_code for entry in self.entries]
        if len(codes) != len(set(codes)):
            msg = "entries must not repeat a course_code"
            raise ValueError(msg)
        if codes != sorted(codes):
            msg = "entries must be ordered by course_code"
            raise ValueError(msg)
        return self

    @property
    def blocked_courses(self) -> tuple[CourseCoordinationEntry, ...]:
        """Entries that cannot be coordinated at all."""
        return tuple(
            entry for entry in self.entries if entry.readiness is CoordinationReadiness.BLOCKED
        )

    @property
    def fully_coordinated_courses(self) -> tuple[CourseCoordinationEntry, ...]:
        """Entries wired across Classroom, Calendar, and academic state."""
        return tuple(
            entry for entry in self.entries if entry.readiness is CoordinationReadiness.READY
        )
