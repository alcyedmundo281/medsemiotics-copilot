"""Unit tests for schedule domain models and date enumeration."""

from datetime import date, time

import pytest
from pydantic import ValidationError

from medsemiotics.domain.schedule import (
    ClassMeetingRule,
    ClassWeekday,
    CourseTeachingSchedule,
    ScheduleException,
    ScheduleExceptionType,
)


class TestClassWeekday:
    """Test suite for ClassWeekday enum and conversions."""

    def test_weekday_from_date(self) -> None:
        """Verify from_date converts Monday..Sunday accurately."""
        # 2026-08-17 is Monday, 2026-08-23 is Sunday
        assert ClassWeekday.from_date(date(2026, 8, 17)) == ClassWeekday.MONDAY
        assert ClassWeekday.from_date(date(2026, 8, 18)) == ClassWeekday.TUESDAY
        assert ClassWeekday.from_date(date(2026, 8, 19)) == ClassWeekday.WEDNESDAY
        assert ClassWeekday.from_date(date(2026, 8, 20)) == ClassWeekday.THURSDAY
        assert ClassWeekday.from_date(date(2026, 8, 21)) == ClassWeekday.FRIDAY
        assert ClassWeekday.from_date(date(2026, 8, 22)) == ClassWeekday.SATURDAY
        assert ClassWeekday.from_date(date(2026, 8, 23)) == ClassWeekday.SUNDAY

    def test_to_weekday_int(self) -> None:
        """Verify to_weekday_int returns standard Python integer values (0..6)."""
        assert ClassWeekday.MONDAY.to_weekday_int() == 0
        assert ClassWeekday.FRIDAY.to_weekday_int() == 4
        assert ClassWeekday.SUNDAY.to_weekday_int() == 6


class TestClassMeetingRule:
    """Test suite for ClassMeetingRule."""

    def test_valid_rule_without_times(self) -> None:
        """Verify valid meeting rule with weekday only."""
        rule = ClassMeetingRule(weekday=ClassWeekday.TUESDAY)
        assert rule.weekday == ClassWeekday.TUESDAY
        assert rule.start_time is None
        assert rule.end_time is None

    def test_valid_rule_with_times(self) -> None:
        """Verify valid meeting rule with ordered start and end times."""
        rule = ClassMeetingRule(
            weekday=ClassWeekday.THURSDAY,
            start_time=time(14, 0),
            end_time=time(16, 0),
        )
        assert rule.start_time == time(14, 0)
        assert rule.end_time == time(16, 0)

    def test_invalid_rule_start_time_after_end_time(self) -> None:
        """Verify start_time >= end_time raises ValidationError."""
        with pytest.raises(ValidationError, match="start_time .* must be strictly before end_time"):
            ClassMeetingRule(
                weekday=ClassWeekday.THURSDAY,
                start_time=time(16, 0),
                end_time=time(14, 0),
            )

    def test_invalid_rule_equal_times(self) -> None:
        """Verify start_time == end_time raises ValidationError."""
        with pytest.raises(ValidationError, match="start_time .* must be strictly before end_time"):
            ClassMeetingRule(
                weekday=ClassWeekday.THURSDAY,
                start_time=time(14, 0),
                end_time=time(14, 0),
            )


class TestCourseTeachingSchedule:
    """Test suite for CourseTeachingSchedule validation and date enumeration."""

    @pytest.fixture
    def active_schedule(self) -> CourseTeachingSchedule:
        """Sample schedule: Tuesdays and Thursdays from Aug 1 to Aug 31, 2026."""
        return CourseTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=True,
            teaching_start_date=date(2026, 8, 1),
            teaching_end_date=date(2026, 8, 31),
            meeting_rules=[
                ClassMeetingRule(weekday=ClassWeekday.TUESDAY),
                ClassMeetingRule(weekday=ClassWeekday.THURSDAY),
            ],
            exceptions=[
                # Aug 11 (Tue): Cancelled
                ScheduleException(
                    date=date(2026, 8, 11),
                    exception_type=ScheduleExceptionType.CANCELLED,
                    notes="National holiday",
                ),
                # Aug 18 (Tue): No Class
                ScheduleException(
                    date=date(2026, 8, 18),
                    exception_type=ScheduleExceptionType.NO_CLASS,
                    notes="Faculty conference",
                ),
                # Aug 21 (Fri): Makeup session
                ScheduleException(
                    date=date(2026, 8, 21),
                    exception_type=ScheduleExceptionType.MAKEUP,
                    notes="Makeup for Aug 11",
                ),
            ],
        )

    def test_is_class_date_matching_weekday(self, active_schedule: CourseTeachingSchedule) -> None:
        """Verify standard Tuesday and Thursday dates return True."""
        # Aug 4 is Tuesday, Aug 6 is Thursday
        assert active_schedule.is_class_date(date(2026, 8, 4)) is True
        assert active_schedule.is_class_date(date(2026, 8, 6)) is True

    def test_is_class_date_non_matching_weekday(self, active_schedule: CourseTeachingSchedule) -> None:
        """Verify non-scheduled weekdays return False."""
        # Aug 3 is Monday, Aug 5 is Wednesday, Aug 7 is Friday
        assert active_schedule.is_class_date(date(2026, 8, 3)) is False
        assert active_schedule.is_class_date(date(2026, 8, 5)) is False
        assert active_schedule.is_class_date(date(2026, 8, 7)) is False

    def test_is_class_date_outside_range(self, active_schedule: CourseTeachingSchedule) -> None:
        """Verify dates before start or after end return False."""
        assert active_schedule.is_class_date(date(2026, 7, 31)) is False
        assert active_schedule.is_class_date(date(2026, 9, 1)) is False

    def test_exceptions_override_rules(self, active_schedule: CourseTeachingSchedule) -> None:
        """Verify cancelled/no_class return False and makeup returns True."""
        # Aug 11 is Tuesday (cancelled) -> False
        assert active_schedule.is_class_date(date(2026, 8, 11)) is False
        # Aug 18 is Tuesday (no_class) -> False
        assert active_schedule.is_class_date(date(2026, 8, 18)) is False
        # Aug 21 is Friday (makeup) -> True
        assert active_schedule.is_class_date(date(2026, 8, 21)) is True

    def test_class_dates_through(self, active_schedule: CourseTeachingSchedule) -> None:
        """Verify class_dates_through enumerates all valid class dates in ascending order."""
        dates = active_schedule.class_dates_through(date(2026, 8, 14))
        # Expected in Aug 1..14:
        # Aug 4 (Tue), Aug 6 (Thu), Aug 11 (cancelled!), Aug 13 (Thu)
        assert dates == [
            date(2026, 8, 4),
            date(2026, 8, 6),
            date(2026, 8, 13),
        ]

    def test_all_class_dates(self, active_schedule: CourseTeachingSchedule) -> None:
        """Verify all_class_dates covers the whole month with makeup added and cancellations removed."""
        all_dates = active_schedule.all_class_dates
        assert date(2026, 8, 11) not in all_dates  # Cancelled
        assert date(2026, 8, 18) not in all_dates  # No class
        assert date(2026, 8, 21) in all_dates      # Makeup Friday
        assert all_dates == sorted(all_dates)

    def test_disabled_schedule_always_empty(self, active_schedule: CourseTeachingSchedule) -> None:
        """Verify disabled schedule returns False for all dates and empty lists for date queries."""
        disabled = CourseTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=False,
            teaching_start_date=date(2026, 8, 1),
            teaching_end_date=date(2026, 8, 31),
            meeting_rules=[ClassMeetingRule(weekday=ClassWeekday.TUESDAY)],
        )
        assert disabled.is_class_date(date(2026, 8, 4)) is False
        assert disabled.class_dates_through(date(2026, 8, 31)) == []
        assert disabled.all_class_dates == []

    def test_target_date_before_start_returns_empty(
        self, active_schedule: CourseTeachingSchedule
    ) -> None:
        """Verify class_dates_through returns empty list when target date is before term start."""
        assert active_schedule.class_dates_through(date(2026, 7, 15)) == []

    def test_invalid_start_after_end(self) -> None:
        """Verify teaching_start_date > teaching_end_date raises ValidationError."""
        with pytest.raises(ValidationError, match="must not be after teaching_end_date"):
            CourseTeachingSchedule(
                semester_id="2026-2",
                course_code="NEURO",
                teaching_start_date=date(2026, 9, 1),
                teaching_end_date=date(2026, 8, 1),
                meeting_rules=[ClassMeetingRule(weekday=ClassWeekday.TUESDAY)],
            )

    def test_duplicate_weekday_rule_rejected(self) -> None:
        """Verify duplicate weekday rules raise ValidationError."""
        with pytest.raises(ValidationError, match="Duplicate meeting rule"):
            CourseTeachingSchedule(
                semester_id="2026-2",
                course_code="NEURO",
                teaching_start_date=date(2026, 8, 1),
                teaching_end_date=date(2026, 8, 31),
                meeting_rules=[
                    ClassMeetingRule(weekday=ClassWeekday.TUESDAY),
                    ClassMeetingRule(weekday=ClassWeekday.TUESDAY),
                ],
            )

    def test_duplicate_exception_date_rejected(self) -> None:
        """Verify duplicate exception dates raise ValidationError."""
        with pytest.raises(ValidationError, match="Duplicate schedule exception"):
            CourseTeachingSchedule(
                semester_id="2026-2",
                course_code="NEURO",
                teaching_start_date=date(2026, 8, 1),
                teaching_end_date=date(2026, 8, 31),
                meeting_rules=[ClassMeetingRule(weekday=ClassWeekday.TUESDAY)],
                exceptions=[
                    ScheduleException(date=date(2026, 8, 11), exception_type=ScheduleExceptionType.CANCELLED),
                    ScheduleException(date=date(2026, 8, 11), exception_type=ScheduleExceptionType.NO_CLASS),
                ],
            )

    def test_exception_outside_teaching_range_rejected(self) -> None:
        """Verify exception date outside start..end raises ValidationError."""
        with pytest.raises(ValidationError, match="falls outside teaching range"):
            CourseTeachingSchedule(
                semester_id="2026-2",
                course_code="NEURO",
                teaching_start_date=date(2026, 8, 1),
                teaching_end_date=date(2026, 8, 31),
                meeting_rules=[ClassMeetingRule(weekday=ClassWeekday.TUESDAY)],
                exceptions=[
                    ScheduleException(date=date(2026, 9, 5), exception_type=ScheduleExceptionType.CANCELLED),
                ],
            )

    def test_empty_meeting_rules_rejected(self) -> None:
        """Verify schedule without meeting rules raises ValidationError."""
        with pytest.raises(ValidationError, match="must have at least one meeting rule"):
            CourseTeachingSchedule(
                semester_id="2026-2",
                course_code="NEURO",
                teaching_start_date=date(2026, 8, 1),
                teaching_end_date=date(2026, 8, 31),
                meeting_rules=[],
            )

    @pytest.mark.parametrize("invalid_val", [123, ["list"], {"dict": 1}])
    def test_schedule_exception_non_string_notes(self, invalid_val: object) -> None:
        """Verify non-string notes raise ValidationError."""
        with pytest.raises(ValidationError):
            ScheduleException(
                date=date(2026, 8, 10),
                exception_type=ScheduleExceptionType.CANCELLED,
                notes=invalid_val,  # type: ignore[arg-type]
            )
