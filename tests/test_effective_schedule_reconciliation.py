"""Unit tests for effective schedule reconciliation engine."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.domain.academic import Course, SemesterConfig
from medsemiotics.domain.calendar import (
    CourseCalendarConfig,
    OperationalCalendarEvent,
)
from medsemiotics.domain.effective_schedule import (
    EffectiveClassSource,
    EffectiveClassStatus,
)
from medsemiotics.domain.exceptions import (
    EffectiveScheduleAmbiguityError,
    EffectiveScheduleError,
)
from medsemiotics.domain.schedule import (
    ClassMeetingRule,
    ClassWeekday,
    CourseTeachingSchedule,
    ScheduleException,
    ScheduleExceptionType,
)
from medsemiotics.services.effective_schedule import (
    build_effective_teaching_schedule,
)


class TestEffectiveScheduleReconciliation:
    """Test suite for build_effective_teaching_schedule reconciliation logic."""

    @pytest.fixture
    def semester(self) -> SemesterConfig:
        return SemesterConfig(
            semester_id="2026-2",
            display_name="2026-2",
            active=True,
            timezone="America/Guayaquil",
            courses=[Course(code="NEURO", name="Neurología")],
        )

    @pytest.fixture
    def baseline_schedule(self) -> CourseTeachingSchedule:
        """Tuesdays and Thursdays in August 2026."""
        return CourseTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=True,
            teaching_start_date=date(2026, 8, 1),
            teaching_end_date=date(2026, 8, 31),
            meeting_rules=[
                ClassMeetingRule(
                    weekday=ClassWeekday.TUESDAY,
                    start_time=time(8, 0),
                    end_time=time(10, 0),
                ),
                ClassMeetingRule(
                    weekday=ClassWeekday.THURSDAY,
                    start_time=time(8, 0),
                    end_time=time(10, 0),
                ),
            ],
            exceptions=[
                ScheduleException(
                    date=date(2026, 8, 11),  # Tuesday holiday
                    exception_type=ScheduleExceptionType.CANCELLED,
                    notes="Feriado",
                ),
            ],
        )

    @pytest.fixture
    def calendar_config(self) -> CourseCalendarConfig:
        return CourseCalendarConfig(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=True,
            calendar_id="cal_neuro",
            aliases=["Neurología", "NEURO"],
            cancellation_markers=["cancelada", "sin clase"],
            makeup_markers=["recuperacion", "recuperación"],
        )

    def test_both_disabled_returns_empty_schedule(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Verify when both baseline and calendar are disabled, returns empty schedule."""
        disabled_sched = baseline_schedule.model_copy(update={"enabled": False})
        disabled_cal = calendar_config.model_copy(update={"enabled": False, "calendar_id": None})

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=disabled_sched,
            calendar_config=disabled_cal,
            calendar_events=[],
        )
        assert effective.events == []
        assert effective.class_dates == []

    def test_baseline_only_calendar_disabled(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Verify baseline-only derivation when calendar is disabled."""
        disabled_cal = calendar_config.model_copy(update={"enabled": False, "calendar_id": None})

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=disabled_cal,
            calendar_events=[],
        )

        assert date(2026, 8, 4) in effective.class_dates
        assert date(2026, 8, 6) in effective.class_dates
        assert date(2026, 8, 11) not in effective.class_dates  # Cancelled baseline exception

        evt_aug4 = next(e for e in effective.events if e.date == date(2026, 8, 4))
        assert evt_aug4.source == EffectiveClassSource.BASELINE
        assert evt_aug4.status == EffectiveClassStatus.SCHEDULED

    def test_example_a_baseline_plus_matching_calendar_event(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Example A: Baseline Tue Aug 18 + Calendar event -> baseline_and_calendar, scheduled."""
        tz = ZoneInfo("America/Guayaquil")
        cal_event = OperationalCalendarEvent(
            event_id="cal_18",
            calendar_id="cal_neuro",
            title="Neurología Clase",
            start=datetime(2026, 8, 18, 8, 30, tzinfo=tz),
            end=datetime(2026, 8, 18, 10, 30, tzinfo=tz),
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[cal_event],
        )

        evt_aug18 = next(e for e in effective.events if e.date == date(2026, 8, 18))
        assert evt_aug18.source == EffectiveClassSource.BASELINE_AND_CALENDAR
        assert evt_aug18.status == EffectiveClassStatus.SCHEDULED
        assert evt_aug18.calendar_event_id == "cal_18"
        assert evt_aug18.start == datetime(2026, 8, 18, 8, 30, tzinfo=tz)

    def test_example_b_calendar_cancellation_marker(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Example B: Baseline Tuesday Aug 25 + Calendar cancellation -> cancelled."""
        tz = ZoneInfo("America/Guayaquil")
        cal_event = OperationalCalendarEvent(
            event_id="cal_25",
            calendar_id="cal_neuro",
            title="Neurología - Clase cancelada por paro",
            start=datetime(2026, 8, 25, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 25, 10, 0, tzinfo=tz),
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[cal_event],
        )

        evt_aug25 = next(e for e in effective.events if e.date == date(2026, 8, 25))
        assert evt_aug25.source == EffectiveClassSource.BASELINE_AND_CALENDAR
        assert evt_aug25.status == EffectiveClassStatus.CANCELLED
        assert date(2026, 8, 25) not in effective.class_dates

    def test_example_c_non_baseline_calendar_event_is_makeup(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Example C: Event on Friday Aug 21 (non-baseline) -> source=calendar, status=makeup."""
        tz = ZoneInfo("America/Guayaquil")
        cal_event = OperationalCalendarEvent(
            event_id="cal_21",
            calendar_id="cal_neuro",
            title="Neurología - Recuperación",
            start=datetime(2026, 8, 21, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 21, 16, 0, tzinfo=tz),
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[cal_event],
        )

        evt_aug21 = next(e for e in effective.events if e.date == date(2026, 8, 21))
        assert evt_aug21.source == EffectiveClassSource.CALENDAR
        assert evt_aug21.status == EffectiveClassStatus.MAKEUP
        assert date(2026, 8, 21) in effective.class_dates

    def test_example_d_calendar_absence_preserves_baseline(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Example D: Baseline Tue Aug 4 without Calendar event remains active scheduled."""
        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[],  # No calendar events at all
        )

        evt_aug4 = next(e for e in effective.events if e.date == date(2026, 8, 4))
        assert evt_aug4.source == EffectiveClassSource.BASELINE
        assert evt_aug4.status == EffectiveClassStatus.SCHEDULED
        assert date(2026, 8, 4) in effective.class_dates

    def test_timezone_conversion_changes_effective_date(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Verify UTC timestamp converts to local date in America/Guayaquil (UTC-5)."""
        utc_start = datetime(2026, 8, 28, 1, 0, tzinfo=ZoneInfo("UTC"))
        utc_end = datetime(2026, 8, 28, 3, 0, tzinfo=ZoneInfo("UTC"))

        cal_event = OperationalCalendarEvent(
            event_id="cal_utc",
            calendar_id="cal_neuro",
            title="Neurología Nocturna",
            start=utc_start,
            end=utc_end,
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[cal_event],
        )

        # In America/Guayaquil (UTC-5), 2026-08-28 01:00 UTC is 2026-08-27 20:00
        evt = next(e for e in effective.events if e.calendar_event_id == "cal_utc")
        assert evt.date == date(2026, 8, 27)
        assert evt.start == datetime(2026, 8, 27, 20, 0, tzinfo=ZoneInfo("America/Guayaquil"))

    def test_cancellation_marker_on_non_baseline_date_ignored(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Verify cancellation marker on non-baseline date does not invent a cancelled class."""
        tz = ZoneInfo("America/Guayaquil")
        cal_event = OperationalCalendarEvent(
            event_id="cal_cancel_wed",
            calendar_id="cal_neuro",
            title="Neurología - Clase cancelada",
            start=datetime(2026, 8, 12, 10, 0, tzinfo=tz),
            end=datetime(2026, 8, 12, 12, 0, tzinfo=tz),
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[cal_event],
        )

        # Should not create any event for Aug 12
        assert not any(e.date == date(2026, 8, 12) for e in effective.events)

    def test_same_date_baseline_normal_plus_cancellation_override(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Case A: 1 normal event + 1 cancellation on baseline date -> cancelled override."""
        tz = ZoneInfo("America/Guayaquil")
        cal_normal = OperationalCalendarEvent(
            event_id="cal_normal_18",
            calendar_id="cal_neuro",
            title="Neurología Clase Ordinaria",
            start=datetime(2026, 8, 18, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 10, 0, tzinfo=tz),
            all_day=False,
        )
        cal_cancel = OperationalCalendarEvent(
            event_id="cal_cancel_18",
            calendar_id="cal_neuro",
            title="Neurología - Clase cancelada por paro docente",
            start=datetime(2026, 8, 18, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 10, 0, tzinfo=tz),
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[cal_normal, cal_cancel],
        )

        # Must produce exactly ONE event for Aug 18
        aug18_events = [e for e in effective.events if e.date == date(2026, 8, 18)]
        assert len(aug18_events) == 1

        evt = aug18_events[0]
        assert evt.status == EffectiveClassStatus.CANCELLED
        assert evt.source == EffectiveClassSource.BASELINE_AND_CALENDAR
        assert evt.calendar_event_id == "cal_cancel_18"
        assert date(2026, 8, 18) not in effective.class_dates

    def test_same_date_baseline_two_normal_events_raises_ambiguity(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Case B: 2 normal active course events on same baseline date -> ambiguity error."""
        tz = ZoneInfo("America/Guayaquil")
        cal_1 = OperationalCalendarEvent(
            event_id="cal_1",
            calendar_id="cal_neuro",
            title="Neurología Sesión Matutina",
            start=datetime(2026, 8, 18, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 10, 0, tzinfo=tz),
            all_day=False,
        )
        cal_2 = OperationalCalendarEvent(
            event_id="cal_2",
            calendar_id="cal_neuro",
            title="Neurología Sesión Vespertina",
            start=datetime(2026, 8, 18, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 16, 0, tzinfo=tz),
            all_day=False,
        )

        with pytest.raises(EffectiveScheduleAmbiguityError, match="Ambiguous calendar evidence"):
            build_effective_teaching_schedule(
                semester=semester,
                schedule=baseline_schedule,
                calendar_config=calendar_config,
                calendar_events=[cal_1, cal_2],
            )

    def test_same_date_baseline_two_cancellation_events_raises_ambiguity(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Case C: 2 cancellation events on same baseline date -> ambiguity error."""
        tz = ZoneInfo("America/Guayaquil")
        cal_1 = OperationalCalendarEvent(
            event_id="cal_c1",
            calendar_id="cal_neuro",
            title="Neurología - cancelada por lluvia",
            start=datetime(2026, 8, 18, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 10, 0, tzinfo=tz),
            all_day=False,
        )
        cal_2 = OperationalCalendarEvent(
            event_id="cal_c2",
            calendar_id="cal_neuro",
            title="Neurología - sin clase aviso de decanato",
            start=datetime(2026, 8, 18, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 10, 0, tzinfo=tz),
            all_day=False,
        )

        with pytest.raises(EffectiveScheduleAmbiguityError, match="Ambiguous calendar evidence"):
            build_effective_teaching_schedule(
                semester=semester,
                schedule=baseline_schedule,
                calendar_config=calendar_config,
                calendar_events=[cal_1, cal_2],
            )

    def test_same_date_baseline_normal_plus_makeup_raises_ambiguity(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Case D: 1 normal event + 1 makeup event on baseline date -> ambiguity error."""
        tz = ZoneInfo("America/Guayaquil")
        cal_normal = OperationalCalendarEvent(
            event_id="cal_norm",
            calendar_id="cal_neuro",
            title="Neurología Clase",
            start=datetime(2026, 8, 18, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 10, 0, tzinfo=tz),
            all_day=False,
        )
        cal_makeup = OperationalCalendarEvent(
            event_id="cal_make",
            calendar_id="cal_neuro",
            title="Neurología - Recuperación",
            start=datetime(2026, 8, 18, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 18, 16, 0, tzinfo=tz),
            all_day=False,
        )

        with pytest.raises(EffectiveScheduleAmbiguityError, match="Ambiguous calendar evidence"):
            build_effective_teaching_schedule(
                semester=semester,
                schedule=baseline_schedule,
                calendar_config=calendar_config,
                calendar_events=[cal_normal, cal_makeup],
            )

    def test_same_date_non_baseline_multiple_events_raises_ambiguity(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Non-baseline date with multiple events -> ambiguity error."""
        tz = ZoneInfo("America/Guayaquil")
        # Aug 21 is Friday (non-baseline)
        cal_1 = OperationalCalendarEvent(
            event_id="cal_fri_1",
            calendar_id="cal_neuro",
            title="Neurología Tutoría",
            start=datetime(2026, 8, 21, 10, 0, tzinfo=tz),
            end=datetime(2026, 8, 21, 12, 0, tzinfo=tz),
            all_day=False,
        )
        cal_2 = OperationalCalendarEvent(
            event_id="cal_fri_2",
            calendar_id="cal_neuro",
            title="Neurología Repaso",
            start=datetime(2026, 8, 21, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 21, 16, 0, tzinfo=tz),
            all_day=False,
        )

        with pytest.raises(EffectiveScheduleAmbiguityError, match="Ambiguous calendar evidence"):
            build_effective_teaching_schedule(
                semester=semester,
                schedule=baseline_schedule,
                calendar_config=calendar_config,
                calendar_events=[cal_1, cal_2],
            )

    def test_scope_mismatch_raises_effective_schedule_error(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Verify scope mismatch raises EffectiveScheduleError."""
        wrong_semester = semester.model_copy(update={"semester_id": "2026-1"})
        with pytest.raises(EffectiveScheduleError, match="Semester mismatch"):
            build_effective_teaching_schedule(
                semester=wrong_semester,
                schedule=baseline_schedule,
                calendar_config=calendar_config,
                calendar_events=[],
            )

        wrong_cal_sem = calendar_config.model_copy(update={"semester_id": "2026-1"})
        with pytest.raises(EffectiveScheduleError, match="Semester mismatch"):
            build_effective_teaching_schedule(
                semester=semester,
                schedule=baseline_schedule,
                calendar_config=wrong_cal_sem,
                calendar_events=[],
            )

        wrong_cal_course = calendar_config.model_copy(update={"course_code": "GASTRO"})
        with pytest.raises(EffectiveScheduleError, match="Course mismatch"):
            build_effective_teaching_schedule(
                semester=semester,
                schedule=baseline_schedule,
                calendar_config=wrong_cal_course,
                calendar_events=[],
            )

    def test_calendar_only_enabled_creates_makeups(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Verify when baseline is disabled, matching calendar events become makeups."""
        tz = ZoneInfo("America/Guayaquil")
        disabled_sched = baseline_schedule.model_copy(update={"enabled": False})

        cal_evt = OperationalCalendarEvent(
            event_id="cal_only",
            calendar_id="cal_neuro",
            title="Neurología Sesión",
            start=datetime(2026, 8, 12, 10, 0, tzinfo=tz),
            end=datetime(2026, 8, 12, 12, 0, tzinfo=tz),
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=disabled_sched,
            calendar_config=calendar_config,
            calendar_events=[cal_evt],
        )

        assert len(effective.events) == 1
        assert effective.events[0].source == EffectiveClassSource.CALENDAR
        assert effective.events[0].status == EffectiveClassStatus.MAKEUP
        assert effective.events[0].date == date(2026, 8, 12)

    def test_makeup_event_on_baseline_cancelled_date(
        self,
        semester: SemesterConfig,
        baseline_schedule: CourseTeachingSchedule,
        calendar_config: CourseCalendarConfig,
    ) -> None:
        """Verify operational event on a baseline holiday/cancelled date is reconciled as makeup."""
        tz = ZoneInfo("America/Guayaquil")
        # Aug 11 is cancelled in baseline fixture
        cal_evt = OperationalCalendarEvent(
            event_id="cal_makeup_holiday",
            calendar_id="cal_neuro",
            title="Neurología Clase Extra en Feriado",
            start=datetime(2026, 8, 11, 10, 0, tzinfo=tz),
            end=datetime(2026, 8, 11, 12, 0, tzinfo=tz),
            all_day=False,
        )

        effective = build_effective_teaching_schedule(
            semester=semester,
            schedule=baseline_schedule,
            calendar_config=calendar_config,
            calendar_events=[cal_evt],
        )

        evt_aug11 = next(e for e in effective.events if e.date == date(2026, 8, 11))
        assert evt_aug11.source == EffectiveClassSource.CALENDAR
        assert evt_aug11.status == EffectiveClassStatus.MAKEUP
        assert date(2026, 8, 11) in effective.class_dates
