"""Domain contracts for deterministic Teaching Coach briefing drafts."""

from datetime import date, datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.academic_state import TopicProgressStatus
from medsemiotics.domain.agents import (
    AgentCapabilityDecision,
    AgentPillar,
    AutonomyLevel,
)
from medsemiotics.domain.coaching import CalendarPublishResult, CoachingBrief
from medsemiotics.domain.teaching_position import TeachingPosition
from medsemiotics.domain.topics import validate_and_normalize_topic_id


def _clean_text(value: object, field_name: str) -> str:
    """Normalize required text and reject blank values."""
    if not isinstance(value, str):
        msg = f"{field_name} must be a string, got {type(value).__name__}"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = f"{field_name} must not be empty or whitespace only"
        raise ValueError(msg)
    return cleaned


def _clean_list(value: object, field_name: str, *, required: bool) -> list[str]:
    """Normalize a unique ordered list of pedagogical statements."""
    if value is None and not required:
        return []
    if not isinstance(value, list):
        msg = f"{field_name} must be a list of strings, got {type(value).__name__}"
        raise ValueError(msg)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        statement = _clean_text(item, f"{field_name} item")
        if statement in seen:
            msg = f"{field_name} contains duplicate value '{statement}'"
            raise ValueError(msg)
        seen.add(statement)
        cleaned.append(statement)

    if required and not cleaned:
        msg = f"{field_name} must contain at least one item"
        raise ValueError(msg)
    return cleaned


class TeachingTopicGuide(BaseModel):
    """Faculty-curated source material for one Teaching Coach draft."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    topic_id: Annotated[str, Field(description="Topic identifier represented by the guide")]
    topic_title: Annotated[str, Field(description="Human-readable teaching topic title")]
    learning_objectives: Annotated[
        list[str], Field(description="Required observable learning objectives")
    ]
    critical_points: Annotated[
        list[str], Field(description="Required clinical or pedagogical emphasis points")
    ]
    teaching_questions: Annotated[
        list[str], Field(default_factory=list, description="Discussion trigger questions")
    ]
    common_pitfalls: Annotated[
        list[str], Field(default_factory=list, description="Frequent misconceptions")
    ]
    material_notes: Annotated[
        list[str], Field(default_factory=list, description="Required teaching materials")
    ]
    assignment_note: Annotated[
        str | None, Field(default=None, description="Optional assignment reminder")
    ]
    powersemiotics_url: Annotated[
        str | None, Field(default=None, description="Optional supporting resource URL")
    ]

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        """Normalize the guide topic identifier."""
        return validate_and_normalize_topic_id(value)

    @field_validator("topic_title", mode="before")
    @classmethod
    def validate_topic_title(cls, value: object) -> str:
        """Normalize the topic title."""
        return _clean_text(value, "topic_title")

    @field_validator("learning_objectives", "critical_points", mode="before")
    @classmethod
    def validate_required_lists(cls, value: object, info: object) -> list[str]:
        """Require substantive objectives and critical points."""
        field_name = getattr(info, "field_name", "list field")
        return _clean_list(value, field_name, required=True)

    @field_validator("teaching_questions", "common_pitfalls", "material_notes", mode="before")
    @classmethod
    def validate_optional_lists(cls, value: object, info: object) -> list[str]:
        """Normalize optional pedagogical lists."""
        field_name = getattr(info, "field_name", "list field")
        return _clean_list(value, field_name, required=False)

    @field_validator("assignment_note", "powersemiotics_url", mode="before")
    @classmethod
    def validate_optional_text(cls, value: object, info: object) -> str | None:
        """Normalize optional text fields and validate the supporting resource URL."""
        if value is None:
            return None
        field_name = getattr(info, "field_name", "field")
        cleaned = _clean_text(value, field_name)
        if field_name == "powersemiotics_url":
            parsed = urlparse(cleaned)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                msg = "powersemiotics_url must be a valid http or https URL"
                raise ValueError(msg)
        return cleaned


class CourseTeachingGuideCatalog(BaseModel):
    """Validated collection of faculty-curated guides for one course and semester."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: str
    course_code: str
    enabled: bool = False
    guides: list[TeachingTopicGuide] = Field(default_factory=list)

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        """Normalize the catalog semester scope."""
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        """Normalize the catalog course scope."""
        return validate_and_normalize_course_code(value)

    @model_validator(mode="after")
    def validate_catalog(self) -> "CourseTeachingGuideCatalog":
        """Require content when enabled and reject ambiguous duplicate topic guides."""
        if self.enabled and not self.guides:
            msg = "enabled teaching guide catalogs must contain at least one guide"
            raise ValueError(msg)
        topic_ids = [guide.topic_id for guide in self.guides]
        duplicates = sorted({topic_id for topic_id in topic_ids if topic_ids.count(topic_id) > 1})
        if duplicates:
            msg = f"duplicate topic guides are not allowed: {duplicates}"
            raise ValueError(msg)
        return self

    def find_guide(self, topic_id: str) -> TeachingTopicGuide | None:
        """Resolve one normalized topic ID without changing catalog state."""
        normalized = validate_and_normalize_topic_id(topic_id)
        return next((guide for guide in self.guides if guide.topic_id == normalized), None)


class CuratedTeachingCoachDraftRequest(BaseModel):
    """Auditable request to draft from one explicitly selected curated topic guide."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: str
    course_code: str
    class_date: date
    time_min: datetime
    time_max: datetime
    topic_id: str
    requested_by: str

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        """Normalize semester scope."""
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        """Normalize course scope."""
        return validate_and_normalize_course_code(value)

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        """Normalize the explicitly requested guide topic."""
        return validate_and_normalize_topic_id(value)

    @field_validator("requested_by", mode="before")
    @classmethod
    def validate_requester(cls, value: object) -> str:
        """Require an accountable requester for the draft audit trail."""
        return _clean_text(value, "requested_by")

    @model_validator(mode="after")
    def validate_time_window(self) -> "CuratedTeachingCoachDraftRequest":
        """Require an ordered timezone-aware calendar evaluation window."""
        for field_name, timestamp in (("time_min", self.time_min), ("time_max", self.time_max)):
            if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
                msg = f"{field_name} must be timezone-aware"
                raise ValueError(msg)
        if self.time_min >= self.time_max:
            msg = "time_min must be strictly before time_max"
            raise ValueError(msg)
        if not self.time_min.date() <= self.class_date <= self.time_max.date():
            msg = "class_date must fall within the calendar evaluation window"
            raise ValueError(msg)
        return self


class TeachingCoachPreviewRequest(BaseModel):
    """Request one reviewable class brief without requiring a caller-selected topic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: str
    course_code: str
    class_date: date
    time_min: datetime
    time_max: datetime
    requested_by: str

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        """Normalize semester scope."""
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        """Normalize course scope."""
        return validate_and_normalize_course_code(value)

    @field_validator("requested_by", mode="before")
    @classmethod
    def validate_requester(cls, value: object) -> str:
        """Require an accountable requester for the preview audit trail."""
        return _clean_text(value, "requested_by")

    @model_validator(mode="after")
    def validate_time_window(self) -> "TeachingCoachPreviewRequest":
        """Require an ordered timezone-aware calendar evaluation window."""
        for field_name, timestamp in (("time_min", self.time_min), ("time_max", self.time_max)):
            if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
                msg = f"{field_name} must be timezone-aware"
                raise ValueError(msg)
        if self.time_min >= self.time_max:
            msg = "time_min must be strictly before time_max"
            raise ValueError(msg)
        if not self.time_min.date() <= self.class_date <= self.time_max.date():
            msg = "class_date must fall within the calendar evaluation window"
            raise ValueError(msg)
        return self


class TeachingCoachDraftRequest(BaseModel):
    """Auditable request to draft one class briefing for an explicit date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: str
    course_code: str
    class_date: date
    time_min: datetime
    time_max: datetime
    guide: TeachingTopicGuide
    requested_by: str

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        """Normalize semester scope."""
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        """Normalize course scope."""
        return validate_and_normalize_course_code(value)

    @field_validator("requested_by", mode="before")
    @classmethod
    def validate_requester(cls, value: object) -> str:
        """Require an accountable requester for the draft audit trail."""
        return _clean_text(value, "requested_by")

    @model_validator(mode="after")
    def validate_time_window(self) -> "TeachingCoachDraftRequest":
        """Require an ordered timezone-aware calendar evaluation window."""
        for field_name, timestamp in (("time_min", self.time_min), ("time_max", self.time_max)):
            if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
                msg = f"{field_name} must be timezone-aware"
                raise ValueError(msg)
        if self.time_min >= self.time_max:
            msg = "time_min must be strictly before time_max"
            raise ValueError(msg)
        if not self.time_min.date() <= self.class_date <= self.time_max.date():
            msg = "class_date must fall within the calendar evaluation window"
            raise ValueError(msg)
        return self


class TeachingCoachDraftResult(BaseModel):
    """Explainable output of one Teaching Coach draft operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brief: CoachingBrief
    teaching_position: TeachingPosition
    topic_status: TopicProgressStatus
    context_notes: list[str]
    capability_decision: AgentCapabilityDecision


class TeachingCoachPreviewResult(BaseModel):
    """Human-reviewable rendering of a deterministic Teaching Coach draft."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    draft: TeachingCoachDraftResult
    preview_title: str
    preview_body: str

    @field_validator("preview_title", "preview_body", mode="before")
    @classmethod
    def validate_preview_text(cls, value: object, info: object) -> str:
        """Reject an empty rendering that could hide an incomplete preview."""
        field_name = getattr(info, "field_name", "preview field")
        return _clean_text(value, field_name)


class TeachingCoachPublishRequest(BaseModel):
    """Request to publish a previously reviewed Teaching Coach draft."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    draft: TeachingCoachDraftResult
    time_min: datetime
    time_max: datetime
    reminders_minutes: list[int] = Field(default_factory=list)
    requested_by: str

    @field_validator("requested_by", mode="before")
    @classmethod
    def validate_requester(cls, value: object) -> str:
        """Require an accountable caller for the publication intent."""
        return _clean_text(value, "requested_by")

    @field_validator("reminders_minutes", mode="before")
    @classmethod
    def validate_reminders(cls, value: object) -> list[int]:
        """Normalize unique positive reminder minutes."""
        if value is None:
            return []
        if not isinstance(value, (list, tuple, set)):
            msg = "reminders_minutes must be a collection of integers"
            raise ValueError(msg)
        reminders: set[int] = set()
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool) or not 0 < item <= 40320:
                msg = "reminders_minutes values must be integers between 1 and 40320"
                raise ValueError(msg)
            reminders.add(item)
        return sorted(reminders)

    @model_validator(mode="after")
    def validate_publish_boundary(self) -> "TeachingCoachPublishRequest":
        """Reject invalid windows and drafts that cannot be traced to the draft capability."""
        for field_name, timestamp in (("time_min", self.time_min), ("time_max", self.time_max)):
            if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
                msg = f"{field_name} must be timezone-aware"
                raise ValueError(msg)
        if self.time_min >= self.time_max:
            msg = "time_min must be strictly before time_max"
            raise ValueError(msg)

        brief = self.draft.brief
        position = self.draft.teaching_position
        if not self.time_min.date() <= brief.class_date <= self.time_max.date():
            msg = "draft class_date must fall within the publication evaluation window"
            raise ValueError(msg)
        if (
            brief.semester_id != position.semester_id
            or brief.course_code != position.course_code
            or brief.class_date != position.target_date
            or brief.topic_id != position.current_topic_id
        ):
            msg = "draft brief does not match its authoritative teaching position"
            raise ValueError(msg)

        decision = self.draft.capability_decision
        if (
            not decision.allowed
            or decision.agent != AgentPillar.COACHING
            or decision.capability_id != "coaching.class-brief"
            or decision.requested_autonomy != AutonomyLevel.DRAFT
        ):
            msg = "draft lacks an allowed coaching.class-brief DRAFT decision"
            raise ValueError(msg)
        return self


class TeachingCoachPublishResult(BaseModel):
    """Auditable result of the separate approved ACT publication step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calendar_result: CalendarPublishResult
    capability_decision: AgentCapabilityDecision
