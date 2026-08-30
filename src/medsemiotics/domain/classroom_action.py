"""Single, explicitly approved, idempotent Google Classroom action contracts.

Loop 0.6E defines what one Classroom write may be and what must be true before it could run. It
carries no execution adapter: a plan is a proposal, and an authorization is a decision, not a call.
"""

import hashlib
import json
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.external_courses import normalize_course_name
from medsemiotics.domain.topics import validate_and_normalize_topic_id


class ClassroomActionType(StrEnum):
    """Classroom write operations this contract is allowed to describe."""

    CREATE_COURSEWORK_DRAFT = "create_coursework_draft"


class ClassroomActionStatus(StrEnum):
    """Outcome of evaluating one planned Classroom action."""

    AUTHORIZED = "authorized"
    ALREADY_APPLIED = "already_applied"
    DENIED = "denied"


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
    """Normalize an optional string, treating blank input as absent."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"{field_name} must be a string or null, got {type(value).__name__}"
        raise ValueError(msg)
    cleaned = value.strip()
    return cleaned or None


def _digest(parts: list[str]) -> str:
    """Build a stable SHA-256 digest over ordered string parts."""
    canonical = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ClassroomActionPlan(BaseModel):
    """One proposed Classroom write, described without any means of executing it.

    The plan can only describe a coursework item created in draft state. It carries no grading
    field, no student list, and no second action: a batch is not representable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_type: Annotated[
        ClassroomActionType, Field(description="The single write this plan describes")
    ]
    semester_id: Annotated[str, Field(description="Academic semester of the target course")]
    course_code: Annotated[str, Field(description="Tracked course code")]
    external_course_id: Annotated[
        str, Field(description="Classroom course id from a decisive coordination link")
    ]
    topic_id: Annotated[str, Field(description="Tracked syllabus topic the work belongs to")]
    title: Annotated[str, Field(description="Coursework title shown to teachers in draft state")]
    instructions: Annotated[str | None, Field(description="Optional coursework instructions")] = (
        None
    )
    due_date: Annotated[date | None, Field(description="Optional local due date")] = None
    prepared_by: Annotated[str, Field(description="Accountable author of the plan")]
    prepared_at: Annotated[datetime, Field(description="Timezone-aware preparation timestamp")]

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        """Normalize the semester identifier."""
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        """Normalize the tracked course code."""
        return validate_and_normalize_course_code(value)

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        """Normalize the tracked topic identifier."""
        return validate_and_normalize_topic_id(value)

    @field_validator("external_course_id", "title", "prepared_by", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require identifying and accountability fields."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("instructions", mode="before")
    @classmethod
    def validate_instructions(cls, value: object) -> str | None:
        """Normalize the optional instructions body."""
        return _clean_optional_text(value, "instructions")

    @field_validator("prepared_at")
    @classmethod
    def validate_prepared_at(cls, value: datetime) -> datetime:
        """Reject naive timestamps so the plan's provenance stays unambiguous."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "prepared_at must be timezone-aware"
            raise ValueError(msg)
        return value

    @field_validator("title")
    @classmethod
    def validate_comparable_title(cls, value: str) -> str:
        """Reject a title that normalizes to nothing, which could never be identified again."""
        if not normalize_course_name(value):
            msg = "title must contain at least one comparable character"
            raise ValueError(msg)
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def identity_key(self) -> str:
        """Stable identity of the work this plan would create.

        Two plans differing only in instructions or due date share one identity, so a re-run
        updates nothing and creates nothing twice.

        Returns:
            Hex SHA-256 digest over the plan's identity fields.
        """
        return _digest(
            [
                str(self.action_type),
                self.semester_id,
                self.course_code,
                self.external_course_id,
                self.topic_id,
                normalize_course_name(self.title),
            ]
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_fingerprint(self) -> str:
        """Digest over everything a reviewer would read before approving.

        Returns:
            Hex SHA-256 digest binding an approval to this exact content.
        """
        return _digest(
            [
                self.identity_key,
                self.title,
                self.instructions or "",
                self.due_date.isoformat() if self.due_date else "",
            ]
        )


class ClassroomActionApproval(BaseModel):
    """Named human approval bound to the exact content of one plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approved_by: Annotated[str, Field(description="Accountable person who approved the plan")]
    approved_at: Annotated[datetime, Field(description="Timezone-aware approval timestamp")]
    content_fingerprint: Annotated[
        str, Field(description="Content fingerprint of the plan that was reviewed")
    ]

    @field_validator("approved_by", "content_fingerprint", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require an accountable approver and the reviewed fingerprint."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("approved_at")
    @classmethod
    def validate_approved_at(cls, value: datetime) -> datetime:
        """Reject naive timestamps so approval evidence stays unambiguous."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "approved_at must be timezone-aware"
            raise ValueError(msg)
        return value


class ClassroomActionRecord(BaseModel):
    """MedSemiotics' own record that one planned action was already applied.

    Coursework reads are outside the authorized Classroom scope, so idempotency is decided against
    this local ledger rather than by querying Classroom.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity_key: Annotated[str, Field(description="Identity of the applied action")]
    external_course_id: Annotated[str, Field(description="Classroom course it was applied to")]
    applied_at: Annotated[datetime, Field(description="Timezone-aware application timestamp")]
    applied_by: Annotated[str, Field(description="Accountable person who applied it")]
    external_reference: Annotated[
        str | None, Field(description="Provider identifier of the created draft")
    ] = None

    @field_validator("identity_key", "external_course_id", "applied_by", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require identity and accountability on every ledger entry."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("external_reference", mode="before")
    @classmethod
    def validate_external_reference(cls, value: object) -> str | None:
        """Normalize the optional provider reference."""
        return _clean_optional_text(value, "external_reference")

    @field_validator("applied_at")
    @classmethod
    def validate_applied_at(cls, value: datetime) -> datetime:
        """Reject naive timestamps so the ledger stays auditable."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "applied_at must be timezone-aware"
            raise ValueError(msg)
        return value


class ClassroomActionDecision(BaseModel):
    """Explainable outcome of evaluating one planned Classroom action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ClassroomActionStatus
    action_type: ClassroomActionType
    identity_key: Annotated[str, Field(description="Identity of the evaluated action")]
    approved_by: Annotated[
        str | None, Field(description="Approver recorded on an authorized action")
    ] = None
    existing_reference: Annotated[
        str | None, Field(description="Provider reference of the previously applied action")
    ] = None
    reason: Annotated[str, Field(description="Why this outcome was reached")]

    @field_validator("identity_key", "reason", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Require an explainable, identifiable decision."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @model_validator(mode="after")
    def validate_decision_evidence(self) -> "ClassroomActionDecision":
        """Only an authorized decision names an approver, and only a repeat names a reference."""
        if self.status is ClassroomActionStatus.AUTHORIZED and self.approved_by is None:
            msg = "An authorized action must record the approver"
            raise ValueError(msg)
        if self.status is not ClassroomActionStatus.AUTHORIZED and self.approved_by is not None:
            msg = f"Status '{self.status.value}' must not record an approver"
            raise ValueError(msg)
        if (
            self.status is not ClassroomActionStatus.ALREADY_APPLIED
            and self.existing_reference is not None
        ):
            msg = f"Status '{self.status.value}' must not name a previously applied action"
            raise ValueError(msg)
        return self
