"""Domain models for effective teaching schedules reconciled from baseline and calendar events."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)


class EffectiveClassSource(StrEnum):
    """Origin source of the reconciled effective class event."""

    BASELINE = "baseline"
    CALENDAR = "calendar"
    BASELINE_AND_CALENDAR = "baseline_and_calendar"


class EffectiveClassStatus(StrEnum):
    """Operational status of the effective class event."""

    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    MOVED = "moved"
    MAKEUP = "makeup"


def _normalize_optional_text(value: object) -> str | None:
    """Trim string and normalize empty/whitespace-only values to None."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"Expected string or None, got {type(value).__name__}"
        raise ValueError(msg)
    trimmed = value.strip()
    return trimmed if trimmed else None


class EffectiveClassEvent(BaseModel):
    """Individual class session outcome reconciled from baseline schedule and external calendar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: Annotated[date, Field(description="Calendar date of the effective class meeting")]
    semester_id: Annotated[str, Field(description="Semester identifier")]
    course_code: Annotated[str, Field(description="Course code")]
    source: Annotated[EffectiveClassSource, Field(description="Origin source of event")]
    status: Annotated[EffectiveClassStatus, Field(description="Operational outcome status")]
    calendar_event_id: Annotated[str | None, Field(description="Linked external event ID")] = None
    title: Annotated[str | None, Field(description="Event display title")] = None
    start: Annotated[datetime | None, Field(description="Timezone-aware start timestamp")] = None
    end: Annotated[datetime | None, Field(description="Timezone-aware end timestamp")] = None
    notes: Annotated[str | None, Field(description="Reconciliation notes")] = None

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

    @field_validator("calendar_event_id", "title", "notes", mode="before")
    @classmethod
    def validate_optional_strings(cls, value: object) -> str | None:
        """Trim optional strings and convert blank values to None."""
        return _normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_event_contract(self) -> "EffectiveClassEvent":
        """Validate timestamp pair presence, timezone awareness, and date alignment."""
        if (self.start is None) != (self.end is None):
            msg = "EffectiveClassEvent requires both start and end to be set, or both to be None."
            raise ValueError(msg)

        if self.start is not None and self.end is not None:
            if self.start.tzinfo is None or self.start.tzinfo.utcoffset(self.start) is None:
                msg = f"start datetime must be timezone-aware (got naive {self.start})."
                raise ValueError(msg)

            if self.end.tzinfo is None or self.end.tzinfo.utcoffset(self.end) is None:
                msg = f"end datetime must be timezone-aware (got naive {self.end})."
                raise ValueError(msg)

            if self.start >= self.end:
                msg = f"start ({self.start}) must be strictly before end ({self.end})."
                raise ValueError(msg)

            if self.date != self.start.date():
                msg = (
                    f"Event date ({self.date}) does not match "
                    f"start timestamp date ({self.start.date()})."
                )
                raise ValueError(msg)

        return self


class EffectiveTeachingSchedule(BaseModel):
    """Complete reconciled teaching calendar across a semester for a course."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Semester identifier")]
    course_code: Annotated[str, Field(description="Course code")]
    timezone: Annotated[str, Field(description="Academic IANA timezone identifier")]
    events: Annotated[
        list[EffectiveClassEvent], Field(default_factory=list, description="Reconciled events")
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

    @field_validator("timezone", mode="before")
    @classmethod
    def validate_timezone(cls, value: object) -> str:
        """Validate that timezone is a valid IANA timezone identifier."""
        if not isinstance(value, str):
            msg = "Timezone must be a string"
            raise ValueError(msg)
        cleaned = value.strip()
        try:
            ZoneInfo(cleaned)
        except Exception as err:
            msg = f"Invalid timezone identifier: '{cleaned}'"
            raise ValueError(msg) from err
        return cleaned

    @property
    def tz(self) -> ZoneInfo:
        """Return the resolved ZoneInfo instance for this schedule."""
        return ZoneInfo(self.timezone)

    @property
    def ordered_events(self) -> list[EffectiveClassEvent]:
        """Return all reconciled events sorted by date, start time, and event ID."""
        # Use a timezone-aware baseline start for sorting when start is None
        min_tz_dt = datetime.min.replace(tzinfo=self.tz)
        return sorted(
            self.events,
            key=lambda e: (
                e.date,
                e.start or min_tz_dt,
                e.calendar_event_id or "",
            ),
        )

    @property
    def class_dates(self) -> list[date]:
        """Return sorted unique dates of active class sessions (scheduled, makeup, moved)."""
        active_statuses = {
            EffectiveClassStatus.SCHEDULED,
            EffectiveClassStatus.MAKEUP,
            EffectiveClassStatus.MOVED,
        }
        active_dates = {e.date for e in self.events if e.status in active_statuses}
        return sorted(active_dates)

    def events_through(self, target_date: date) -> list[EffectiveClassEvent]:
        """Return all ordered reconciled events occurring on or before target_date."""
        return [e for e in self.ordered_events if e.date <= target_date]

    def class_dates_through(self, target_date: date) -> list[date]:
        """Return all active class dates occurring on or before target_date."""
        return [d for d in self.class_dates if d <= target_date]

    def is_class_date(self, target_date: date) -> bool:
        """Return True if target_date is an active scheduled class date."""
        return target_date in self.class_dates
