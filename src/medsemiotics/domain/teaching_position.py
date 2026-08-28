"""Domain models for teaching calendar position and pacing analysis."""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.topics import validate_and_normalize_topic_id


class TeachingPaceStatus(StrEnum):
    """Evaluation status of actual teaching progress against planned curriculum pacing."""

    AHEAD = "ahead"
    ON_TRACK = "on_track"
    BEHIND = "behind"
    NOT_STARTED = "not_started"
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


class TeachingPosition(BaseModel):
    """Deterministic snapshot of course pacing and topic coverage for a specific target date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Semester identifier")]
    course_code: Annotated[str, Field(description="Course code")]
    target_date: Annotated[date, Field(description="Reference evaluation date")]
    is_class_date: Annotated[
        bool, Field(description="Whether class is scheduled on the target date")
    ]
    expected_session_count: Annotated[
        int, Field(ge=0, description="Scheduled class meetings through target date")
    ]
    actual_session_count: Annotated[
        int, Field(ge=0, description="Historical class meetings through target date")
    ]
    expected_topic_order: Annotated[
        int | None,
        Field(
            default=None,
            ge=1,
            description="Expected planned topic order corresponding to session slot",
        ),
    ]
    current_topic_id: Annotated[
        str | None,
        Field(default=None, description="Current next required topic identifier needing coverage"),
    ]
    pace_status: Annotated[TeachingPaceStatus, Field(description="Pacing assessment")]
    topic_delta: Annotated[
        int | None,
        Field(
            default=None, description="Completed topic position minus expected completed position"
        ),
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

    @field_validator("current_topic_id", mode="before")
    @classmethod
    def validate_current_topic_id(cls, value: object) -> str | None:
        """Validate and normalize current_topic_id if provided."""
        if value is None:
            return None
        return validate_and_normalize_topic_id(value)
