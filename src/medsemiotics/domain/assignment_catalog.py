"""Faculty-reviewed assignment and qualitative-rubric catalog contracts."""

import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.classroom_action import ClassroomActionPlan
from medsemiotics.domain.topics import validate_and_normalize_topic_id

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _clean_required_text(value: object, field_name: str) -> str:
    """Normalize required human-readable text."""
    if not isinstance(value, str):
        msg = f"{field_name} must be a string, got {type(value).__name__}"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = f"{field_name} must not be empty or whitespace only"
        raise ValueError(msg)
    return cleaned


def _clean_slug(value: object, field_name: str) -> str:
    """Normalize a stable public identifier."""
    cleaned = _clean_required_text(value, field_name).lower()
    if not _SLUG_PATTERN.fullmatch(cleaned):
        msg = f"{field_name} must use lowercase letters, digits, and single hyphens"
        raise ValueError(msg)
    return cleaned


def _clean_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    """Require a non-empty ordered list of unique text values."""
    if not isinstance(value, list | tuple):
        msg = f"{field_name} must be an ordered list or tuple"
        raise ValueError(msg)
    items = tuple(_clean_required_text(item, field_name) for item in value)
    if not items:
        msg = f"{field_name} must contain at least one item"
        raise ValueError(msg)
    if len(items) != len(set(items)):
        msg = f"{field_name} must not contain duplicate values"
        raise ValueError(msg)
    return items


class RubricLevel(BaseModel):
    """One qualitative performance level; it carries no student score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level_id: Annotated[str, Field(description="Stable qualitative level identifier")]
    label: Annotated[str, Field(description="Faculty-facing level label")]
    description: Annotated[str, Field(description="General interpretation of the level")]

    @field_validator("level_id", mode="before")
    @classmethod
    def validate_level_id(cls, value: object) -> str:
        return _clean_slug(value, "level_id")

    @field_validator("label", "description", mode="before")
    @classmethod
    def validate_text(cls, value: object, info: object) -> str:
        return _clean_required_text(value, getattr(info, "field_name", "field"))


class RubricCriterion(BaseModel):
    """A weighted review dimension, not a recorded student grade."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    criterion_id: Annotated[str, Field(description="Stable criterion identifier")]
    title: Annotated[str, Field(description="Short criterion label")]
    description: Annotated[str, Field(description="What faculty should look for")]
    weight_percent: Annotated[int, Field(ge=1, le=100, description="Relative review weight")]

    @field_validator("criterion_id", mode="before")
    @classmethod
    def validate_criterion_id(cls, value: object) -> str:
        return _clean_slug(value, "criterion_id")

    @field_validator("title", "description", mode="before")
    @classmethod
    def validate_text(cls, value: object, info: object) -> str:
        return _clean_required_text(value, getattr(info, "field_name", "field"))


class AssignmentRubric(BaseModel):
    """Reusable qualitative rubric whose weights total one hundred percent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rubric_id: Annotated[str, Field(description="Stable rubric identifier")]
    title: Annotated[str, Field(description="Faculty-facing rubric title")]
    levels: Annotated[tuple[RubricLevel, ...], Field(min_length=2)]
    criteria: Annotated[tuple[RubricCriterion, ...], Field(min_length=1)]

    @field_validator("rubric_id", mode="before")
    @classmethod
    def validate_rubric_id(cls, value: object) -> str:
        return _clean_slug(value, "rubric_id")

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return _clean_required_text(value, "title")

    @model_validator(mode="after")
    def validate_rubric_integrity(self) -> "AssignmentRubric":
        level_ids = [level.level_id for level in self.levels]
        if len(level_ids) != len(set(level_ids)):
            raise ValueError("rubric levels must not repeat a level_id")
        criterion_ids = [criterion.criterion_id for criterion in self.criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("rubric criteria must not repeat a criterion_id")
        total_weight = sum(criterion.weight_percent for criterion in self.criteria)
        if total_weight != 100:
            msg = f"rubric criterion weights must total 100, got {total_weight}"
            raise ValueError(msg)
        return self


class AssignmentTemplate(BaseModel):
    """One faculty-reviewed assignment template aligned to a syllabus topic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    assignment_id: Annotated[str, Field(description="Stable assignment identifier")]
    topic_id: Annotated[str, Field(description="Tracked syllabus topic")]
    title: Annotated[str, Field(description="Suggested Classroom title")]
    prompt: Annotated[str, Field(description="Faculty-reviewed assignment prompt")]
    deliverables: Annotated[tuple[str, ...], Field(min_length=1)]
    rubric_id: Annotated[str, Field(description="Referenced rubric identifier")]
    suggested_due_days: Annotated[int, Field(ge=1, le=30)] = 7

    @field_validator("assignment_id", mode="before")
    @classmethod
    def validate_assignment_id(cls, value: object) -> str:
        return _clean_slug(value, "assignment_id")

    @field_validator("rubric_id", mode="before")
    @classmethod
    def validate_rubric_id(cls, value: object) -> str:
        return _clean_slug(value, "rubric_id")

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        return validate_and_normalize_topic_id(value)

    @field_validator("title", "prompt", mode="before")
    @classmethod
    def validate_text(cls, value: object, info: object) -> str:
        return _clean_required_text(value, getattr(info, "field_name", "field"))

    @field_validator("deliverables", mode="before")
    @classmethod
    def validate_deliverables(cls, value: object) -> tuple[str, ...]:
        return _clean_text_tuple(value, "deliverables")


class CourseAssignmentCatalog(BaseModel):
    """Public assignment/rubric catalog for one course and semester."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: str
    course_code: str
    enabled: bool = False
    assignments: tuple[AssignmentTemplate, ...] = ()
    rubrics: tuple[AssignmentRubric, ...] = ()

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        return validate_and_normalize_course_code(value)

    @model_validator(mode="after")
    def validate_catalog_integrity(self) -> "CourseAssignmentCatalog":
        if self.enabled and (not self.assignments or not self.rubrics):
            raise ValueError("an enabled assignment catalog requires assignments and rubrics")

        assignment_ids = [assignment.assignment_id for assignment in self.assignments]
        if len(assignment_ids) != len(set(assignment_ids)):
            raise ValueError("assignment catalog must not repeat an assignment_id")

        rubric_ids = [rubric.rubric_id for rubric in self.rubrics]
        if len(rubric_ids) != len(set(rubric_ids)):
            raise ValueError("assignment catalog must not repeat a rubric_id")

        known_rubrics = set(rubric_ids)
        missing = sorted(
            {
                assignment.rubric_id
                for assignment in self.assignments
                if assignment.rubric_id not in known_rubrics
            }
        )
        if missing:
            msg = f"assignments reference unknown rubric ids: {missing}"
            raise ValueError(msg)
        return self

    def find_assignment(self, assignment_id: str) -> AssignmentTemplate | None:
        normalized = _clean_slug(assignment_id, "assignment_id")
        return next(
            (item for item in self.assignments if item.assignment_id == normalized),
            None,
        )

    def find_rubric(self, rubric_id: str) -> AssignmentRubric | None:
        normalized = _clean_slug(rubric_id, "rubric_id")
        return next((item for item in self.rubrics if item.rubric_id == normalized), None)


class CatalogAssignmentDraftRequest(BaseModel):
    """Mobile-friendly request for one catalog-backed Classroom draft plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: str
    course_code: str
    assignment_id: str
    due_date: date
    prepared_by: str

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        return validate_and_normalize_course_code(value)

    @field_validator("assignment_id", mode="before")
    @classmethod
    def validate_assignment_id(cls, value: object) -> str:
        return _clean_slug(value, "assignment_id")

    @field_validator("prepared_by", mode="before")
    @classmethod
    def validate_prepared_by(cls, value: object) -> str:
        return _clean_required_text(value, "prepared_by")


class CatalogAssignmentDraft(BaseModel):
    """Reviewable catalog content plus the existing non-executing Classroom plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    assignment: AssignmentTemplate
    rubric: AssignmentRubric
    plan: ClassroomActionPlan

    @model_validator(mode="after")
    def validate_alignment(self) -> "CatalogAssignmentDraft":
        if self.assignment.rubric_id != self.rubric.rubric_id:
            raise ValueError("draft assignment and rubric are not aligned")
        if self.assignment.topic_id != self.plan.topic_id:
            raise ValueError("draft assignment and Classroom plan use different topics")
        if self.assignment.title != self.plan.title:
            raise ValueError("draft assignment and Classroom plan use different titles")
        return self
