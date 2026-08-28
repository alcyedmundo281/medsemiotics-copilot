"""Deterministic reconciliation engine deriving effective teaching schedules."""

from collections.abc import Collection
from datetime import date, datetime, timedelta

from medsemiotics.domain.academic import SemesterConfig
from medsemiotics.domain.calendar import (
    CourseCalendarConfig,
    OperationalCalendarEvent,
)
from medsemiotics.domain.effective_schedule import (
    EffectiveClassEvent,
    EffectiveClassSource,
    EffectiveClassStatus,
    EffectiveTeachingSchedule,
)
from medsemiotics.domain.exceptions import (
    EffectiveScheduleAmbiguityError,
    EffectiveScheduleError,
)
from medsemiotics.domain.schedule import (
    ClassWeekday,
    CourseTeachingSchedule,
    ScheduleExceptionType,
)


def _validate_reconciliation_scope(
    semester: SemesterConfig,
    schedule: CourseTeachingSchedule,
    calendar_config: CourseCalendarConfig,
) -> None:
    """Validate that semester, schedule, and calendar_config scopes are aligned."""
    if schedule.semester_id != semester.semester_id:
        msg = (
            f"Semester mismatch between semester config ('{semester.semester_id}') "
            f"and teaching schedule ('{schedule.semester_id}')."
        )
        raise EffectiveScheduleError(msg)

    if calendar_config.semester_id != semester.semester_id:
        msg = (
            f"Semester mismatch between semester config ('{semester.semester_id}') "
            f"and calendar config ('{calendar_config.semester_id}')."
        )
        raise EffectiveScheduleError(msg)

    if calendar_config.course_code != schedule.course_code:
        msg = (
            f"Course mismatch between teaching schedule ('{schedule.course_code}') "
            f"and calendar config ('{calendar_config.course_code}')."
        )
        raise EffectiveScheduleError(msg)


def build_effective_teaching_schedule(
    *,
    semester: SemesterConfig,
    schedule: CourseTeachingSchedule,
    calendar_config: CourseCalendarConfig,
    calendar_events: Collection[OperationalCalendarEvent],
) -> EffectiveTeachingSchedule:
    """Derive deterministic EffectiveTeachingSchedule from baseline schedule and calendar events.

    Args:
        semester: Validated SemesterConfig providing authoritative timezone.
        schedule: Baseline CourseTeachingSchedule.
        calendar_config: CourseCalendarConfig with aliases and markers.
        calendar_events: Pre-filtered OperationalCalendarEvent instances for this course.

    Returns:
        Reconciled EffectiveTeachingSchedule.

    Raises:
        EffectiveScheduleError: If scopes mismatch or timezone is invalid.
        EffectiveScheduleAmbiguityError: If conflicting multiple calendar events occur on the same date.
    """
    _validate_reconciliation_scope(semester, schedule, calendar_config)

    semester_id = schedule.semester_id
    course_code = schedule.course_code
    tz = semester.tz

    if not schedule.enabled and not calendar_config.enabled:
        return EffectiveTeachingSchedule(
            semester_id=semester_id,
            course_code=course_code,
            timezone=semester.timezone,
            events=[],
        )

    # 1. Build baseline active and cancelled day maps
    active_baseline: dict[date, tuple[datetime | None, datetime | None]] = {}
    cancelled_baseline: dict[date, str | None] = {}

    if schedule.enabled:
        scheduled_weekdays = {r.weekday: r for r in schedule.meeting_rules}
        exception_map = {exc.date: exc for exc in schedule.exceptions}

        curr = schedule.teaching_start_date
        while curr <= schedule.teaching_end_date:
            curr_weekday = ClassWeekday.from_date(curr)
            rule = scheduled_weekdays.get(curr_weekday)

            if schedule.is_class_date(curr):
                if rule and rule.start_time and rule.end_time:
                    b_start: datetime | None = datetime.combine(curr, rule.start_time, tzinfo=tz)
                    b_end: datetime | None = datetime.combine(curr, rule.end_time, tzinfo=tz)
                else:
                    b_start = None
                    b_end = None
                active_baseline[curr] = (b_start, b_end)
            elif curr in exception_map:
                exc = exception_map[curr]
                if (
                    exc.exception_type in (ScheduleExceptionType.CANCELLED, ScheduleExceptionType.NO_CLASS)
                    and curr_weekday in scheduled_weekdays
                ):
                    cancelled_baseline[curr] = exc.notes

            curr += timedelta(days=1)

    # 2. Group and interpret operational calendar events in academic timezone
    cal_events_by_date: dict[date, list[tuple[OperationalCalendarEvent, bool, bool]]] = {}
    if calendar_config.enabled:
        for event in calendar_events:
            local_start = event.start.astimezone(tz)
            local_date = local_start.date()

            title_lower = event.title.lower()
            is_cancel = any(
                m.lower() in title_lower
                for m in calendar_config.cancellation_markers
                if m.strip()
            )
            is_makeup = any(
                m.lower() in title_lower
                for m in calendar_config.makeup_markers
                if m.strip()
            )

            cal_events_by_date.setdefault(local_date, []).append((event, is_cancel, is_makeup))

    # Check same-date calendar ambiguity and resolve deterministic cancellation overrides
    cal_single_by_date: dict[date, tuple[OperationalCalendarEvent, bool, bool]] = {}
    for d, evts in cal_events_by_date.items():
        if len(evts) == 1:
            cal_single_by_date[d] = evts[0]
        elif len(evts) == 2 and d in active_baseline:
            # Narrow deterministic exception: 1 normal event + 1 explicit cancellation event on active baseline date
            cancel_events = [e for e in evts if e[1] is True]
            normal_events = [e for e in evts if e[1] is False and e[2] is False]
            if len(cancel_events) == 1 and len(normal_events) == 1:
                # Explicit cancellation signal overrides normal course event
                cal_single_by_date[d] = cancel_events[0]
            else:
                titles = [e[0].title for e in evts]
                msg = f"Ambiguous calendar evidence: multiple events found on date {d} for {course_code}: {titles}"
                raise EffectiveScheduleAmbiguityError(msg)
        else:
            titles = [e[0].title for e in evts]
            msg = f"Ambiguous calendar evidence: multiple events found on date {d} for {course_code}: {titles}"
            raise EffectiveScheduleAmbiguityError(msg)

    # 3. Perform reconciliation
    reconciled_events: list[EffectiveClassEvent] = []
    handled_calendar_dates: set[date] = set()

    if schedule.enabled and not calendar_config.enabled:
        for d, (b_start, b_end) in active_baseline.items():
            reconciled_events.append(
                EffectiveClassEvent(
                    date=d,
                    semester_id=semester_id,
                    course_code=course_code,
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                    start=b_start,
                    end=b_end,
                )
            )
        for d, notes in cancelled_baseline.items():
            reconciled_events.append(
                EffectiveClassEvent(
                    date=d,
                    semester_id=semester_id,
                    course_code=course_code,
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.CANCELLED,
                    notes=notes,
                )
            )

    elif not schedule.enabled and calendar_config.enabled:
        for d, (cal_ev, is_cancel, _is_makeup) in cal_single_by_date.items():
            if is_cancel:
                # Cancellation marker on non-baseline date is ignored
                continue
            local_start = cal_ev.start.astimezone(tz)
            local_end = cal_ev.end.astimezone(tz)
            reconciled_events.append(
                EffectiveClassEvent(
                    date=d,
                    semester_id=semester_id,
                    course_code=course_code,
                    source=EffectiveClassSource.CALENDAR,
                    status=EffectiveClassStatus.MAKEUP,
                    calendar_event_id=cal_ev.event_id,
                    title=cal_ev.title,
                    start=local_start,
                    end=local_end,
                )
            )

    else:
        # Both baseline and calendar are enabled
        for d, (b_start, b_end) in active_baseline.items():
            if d in cal_single_by_date:
                cal_ev, is_cancel, _is_makeup = cal_single_by_date[d]
                handled_calendar_dates.add(d)
                local_start = cal_ev.start.astimezone(tz)
                local_end = cal_ev.end.astimezone(tz)
                if is_cancel:
                    reconciled_events.append(
                        EffectiveClassEvent(
                            date=d,
                            semester_id=semester_id,
                            course_code=course_code,
                            source=EffectiveClassSource.BASELINE_AND_CALENDAR,
                            status=EffectiveClassStatus.CANCELLED,
                            calendar_event_id=cal_ev.event_id,
                            title=cal_ev.title,
                            start=local_start,
                            end=local_end,
                        )
                    )
                else:
                    reconciled_events.append(
                        EffectiveClassEvent(
                            date=d,
                            semester_id=semester_id,
                            course_code=course_code,
                            source=EffectiveClassSource.BASELINE_AND_CALENDAR,
                            status=EffectiveClassStatus.SCHEDULED,
                            calendar_event_id=cal_ev.event_id,
                            title=cal_ev.title,
                            start=local_start,
                            end=local_end,
                        )
                    )
            else:
                # Calendar absence preserves baseline!
                reconciled_events.append(
                    EffectiveClassEvent(
                        date=d,
                        semester_id=semester_id,
                        course_code=course_code,
                        source=EffectiveClassSource.BASELINE,
                        status=EffectiveClassStatus.SCHEDULED,
                        start=b_start,
                        end=b_end,
                    )
                )

        for d, notes in cancelled_baseline.items():
            if d in cal_single_by_date:
                cal_ev, is_cancel, _is_makeup = cal_single_by_date[d]
                handled_calendar_dates.add(d)
                local_start = cal_ev.start.astimezone(tz)
                local_end = cal_ev.end.astimezone(tz)
                if is_cancel:
                    reconciled_events.append(
                        EffectiveClassEvent(
                            date=d,
                            semester_id=semester_id,
                            course_code=course_code,
                            source=EffectiveClassSource.BASELINE_AND_CALENDAR,
                            status=EffectiveClassStatus.CANCELLED,
                            calendar_event_id=cal_ev.event_id,
                            title=cal_ev.title,
                            start=local_start,
                            end=local_end,
                            notes=notes,
                        )
                    )
                else:
                    # Makeup class occurring on a baseline-cancelled date
                    reconciled_events.append(
                        EffectiveClassEvent(
                            date=d,
                            semester_id=semester_id,
                            course_code=course_code,
                            source=EffectiveClassSource.CALENDAR,
                            status=EffectiveClassStatus.MAKEUP,
                            calendar_event_id=cal_ev.event_id,
                            title=cal_ev.title,
                            start=local_start,
                            end=local_end,
                            notes=notes,
                        )
                    )
            else:
                reconciled_events.append(
                    EffectiveClassEvent(
                        date=d,
                        semester_id=semester_id,
                        course_code=course_code,
                        source=EffectiveClassSource.BASELINE,
                        status=EffectiveClassStatus.CANCELLED,
                        notes=notes,
                    )
                )

        # Unhandled calendar events on non-baseline dates
        for d, (cal_ev, is_cancel, _is_makeup) in cal_single_by_date.items():
            if d not in handled_calendar_dates:
                if is_cancel:
                    # Cancellation marker on non-baseline date is ignored
                    continue
                local_start = cal_ev.start.astimezone(tz)
                local_end = cal_ev.end.astimezone(tz)
                reconciled_events.append(
                    EffectiveClassEvent(
                        date=d,
                        semester_id=semester_id,
                        course_code=course_code,
                        source=EffectiveClassSource.CALENDAR,
                        status=EffectiveClassStatus.MAKEUP,
                        calendar_event_id=cal_ev.event_id,
                        title=cal_ev.title,
                        start=local_start,
                        end=local_end,
                    )
                )

    schedule_instance = EffectiveTeachingSchedule(
        semester_id=semester_id,
        course_code=course_code,
        timezone=semester.timezone,
        events=reconciled_events,
    )
    return schedule_instance
