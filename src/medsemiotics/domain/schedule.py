"""Domain models for class meeting rules, calendar schedules, and exceptions."""

from datetime import date, time, timedelta
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)


class ClassWeekday(StrEnum):
    """Day of the week for recurring class meetings."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @classmethod
    def from_date(cls, d: date) -> "ClassWeekday":
        """Convert a standard Python date to the corresponding ClassWeekday enum."""
        weekdays = [
            cls.MONDAY,
            cls.TUESDAY,
            cls.WEDNESDAY,
            cls.THURSDAY,
            cls.FRIDAY,
            cls.SATURDAY,
            cls.SUNDAY,
        ]
        return weekdays[d.weekday()]

    def to_weekday_int(self) -> int:
        """Return the integer representation compatible with date.weekday() (0=Monday, 6=Sunday)."""
        weekdays = [
            ClassWeekday.MONDAY,
            ClassWeekday.TUESDAY,
            ClassWeekday.WEDNESDAY,
            ClassWeekday.THURSDAY,
            ClassWeekday.FRIDAY,
            ClassWeekday.SATURDAY,
            ClassWeekday.SUNDAY,
        ]
        return weekdays.index(self)


class ClassMeetingRule(BaseModel):
    """Recurring weekly meeting rule for a course."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    weekday: Annotated[ClassWeekday, Field(description="Day of the week for class")]
    start_time: Annotated[time | None, Field(default=None, description="Optional class start time")]
    end_time: Annotated[time | None, Field(default=None, description="Optional class end time")]

    @model_validator(mode="after")
    def validate_times(self) -> "ClassMeetingRule":
        """Validate that start_time is strictly before end_time if both are provided."""
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time >= self.end_time
        ):
            msg = (
                f"start_time ({self.start_time}) must be strictly before "
                f"end_time ({self.end_time})."
            )
            raise ValueError(msg)
        return self


class ScheduleExceptionType(StrEnum):
    """Types of calendar exceptions overriding standard weekly meeting rules."""

    CANCELLED = "cancelled"
    MAKEUP = "makeup"
    NO_CLASS = "no_class"


class ScheduleException(BaseModel):
    """Calendar exception for a specific date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: Annotated[date, Field(description="Date of the schedule exception")]
    exception_type: Annotated[ScheduleExceptionType, Field(description="Type of exception")]
    notes: Annotated[str | None, Field(default=None, description="Optional explanation")]

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, value: object) -> str | None:
        """Trim notes and convert empty strings to None."""
        if value is None:
            return None
        if not isinstance(value, str):
            msg = "Notes must be a string or None"
            raise ValueError(msg)
        trimmed = value.strip()
        return trimmed if trimmed else None


class CourseTeachingSchedule(BaseModel):
    """Complete institutional teaching schedule for a course across a semester."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semester_id: Annotated[str, Field(description="Semester identifier, e.g. '2026-2'")]
    course_code: Annotated[str, Field(description="Course code, e.g. 'NEURO'")]
    enabled: bool = True
    teaching_start_date: Annotated[
        date, Field(description="First calendar day of the academic term")
    ]
    teaching_end_date: Annotated[date, Field(description="Last calendar day of the academic term")]
    meeting_rules: list[ClassMeetingRule]
    exceptions: list[ScheduleException] = []

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

    @model_validator(mode="after")
    def validate_schedule_integrity(self) -> "CourseTeachingSchedule":
        """Validate date ordering, rule uniqueness, and exception containment."""
        if self.teaching_start_date > self.teaching_end_date:
            msg = (
                f"teaching_start_date ({self.teaching_start_date}) must not be after "
                f"teaching_end_date ({self.teaching_end_date})."
            )
            raise ValueError(msg)

        if not self.meeting_rules:
            msg = (
                f"Schedule for {self.course_code} ({self.semester_id}) "
                "must have at least one meeting rule."
            )
            raise ValueError(msg)

        seen_weekdays: set[ClassWeekday] = set()
        for rule in self.meeting_rules:
            if rule.weekday in seen_weekdays:
                msg = (
                    f"Duplicate meeting rule for weekday '{rule.weekday.value}' "
                    f"in schedule {self.course_code}."
                )
                raise ValueError(msg)
            seen_weekdays.add(rule.weekday)

        seen_exceptions: set[date] = set()
        for exc in self.exceptions:
            if exc.date in seen_exceptions:
                msg = (
                    f"Duplicate schedule exception for date '{exc.date}' "
                    f"in schedule {self.course_code}."
                )
                raise ValueError(msg)
            seen_exceptions.add(exc.date)

            if exc.date < self.teaching_start_date or exc.date > self.teaching_end_date:
                msg = (
                    f"Schedule exception date '{exc.date}' falls outside teaching range "
                    f"[{self.teaching_start_date} .. {self.teaching_end_date}]."
                )
                raise ValueError(msg)

        return self

    def is_class_date(self, target_date: date) -> bool:
        """Determine whether class is scheduled to occur on the given target date.

        Rules:
            - If disabled -> False
            - Outside [teaching_start_date .. teaching_end_date] -> False
            - Explicit CANCELLED or NO_CLASS exception on date -> False
            - Explicit MAKEUP exception on date -> True
            - Matches recurring ClassMeetingRule weekday -> True
            - Otherwise -> False
        """
        if not self.enabled:
            return False

        if target_date < self.teaching_start_date or target_date > self.teaching_end_date:
            return False

        exception_map = {exc.date: exc.exception_type for exc in self.exceptions}
        if target_date in exception_map:
            exc_type = exception_map[target_date]
            if exc_type in (ScheduleExceptionType.CANCELLED, ScheduleExceptionType.NO_CLASS):
                return False
            if exc_type == ScheduleExceptionType.MAKEUP:
                return True

        target_weekday = ClassWeekday.from_date(target_date)
        scheduled_weekdays = {rule.weekday for rule in self.meeting_rules}
        return target_weekday in scheduled_weekdays

    def class_dates_through(self, target_date: date) -> list[date]:
        """Enumerate scheduled class dates through target_date.

        Returns empty list if schedule is disabled or target_date is before start.
        """
        if not self.enabled:
            return []

        if target_date < self.teaching_start_date:
            return []

        effective_end = min(target_date, self.teaching_end_date)
        class_dates: list[date] = []
        current = self.teaching_start_date
        while current <= effective_end:
            if self.is_class_date(current):
                class_dates.append(current)
            current += timedelta(days=1)

        return class_dates

    @property
    def all_class_dates(self) -> list[date]:
        """Return all scheduled class dates across the entire academic term."""
        return self.class_dates_through(self.teaching_end_date)
