"""Unit tests for EffectiveScheduleService orchestration."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.domain.calendar import OperationalCalendarEvent
from medsemiotics.domain.effective_schedule import EffectiveClassSource
from medsemiotics.domain.exceptions import (
    CalendarConfigError,
    SemesterConfigNotFoundError,
)
from medsemiotics.integrations.google_calendar.client import GoogleCalendarReader
from medsemiotics.services.calendar_config_repository import (
    CalendarConfigRepository,
)
from medsemiotics.services.effective_schedule_service import (
    EffectiveScheduleService,
)
from medsemiotics.services.schedule_repository import ScheduleRepository
from medsemiotics.services.semester_repository import SemesterRepository


class TestEffectiveScheduleService:
    """Test suite for EffectiveScheduleService."""

    @pytest.fixture
    def setup_repos(
        self, tmp_path: Path
    ) -> tuple[SemesterRepository, ScheduleRepository, CalendarConfigRepository, Path]:
        sem_dir = tmp_path / "semesters"
        sched_dir = tmp_path / "schedules"
        cal_dir = tmp_path / "calendar"

        sem_dir.mkdir(parents=True)
        (sched_dir / "2026-2").mkdir(parents=True)
        (cal_dir / "2026-2").mkdir(parents=True)

        (sem_dir / "2026-2.yaml").write_text(
            """
semester_id: "2026-2"
display_name: "2026-2"
active: true
timezone: "America/Guayaquil"
courses:
  - code: "NEURO"
    name: "Neurología"
""",
            encoding="utf-8",
        )

        (sched_dir / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
enabled: true
teaching_start_date: "2026-08-01"
teaching_end_date: "2026-08-31"
meeting_rules:
  - weekday: "tuesday"
exceptions: []
""",
            encoding="utf-8",
        )

        (cal_dir / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
enabled: false
calendar_id: null
aliases:
  - "Neurología"
  - "NEURO"
""",
            encoding="utf-8",
        )

        return (
            SemesterRepository(sem_dir),
            ScheduleRepository(sched_dir),
            CalendarConfigRepository(cal_dir),
            tmp_path,
        )

    def test_disabled_calendar_does_not_call_google_reader(
        self,
        setup_repos: tuple[SemesterRepository, ScheduleRepository, CalendarConfigRepository, Path],
    ) -> None:
        """Verify when calendar_config.enabled is False, GoogleCalendarReader is never called."""
        sem_repo, sched_repo, cal_repo, _ = setup_repos
        mock_reader = MagicMock(spec=GoogleCalendarReader)

        service = EffectiveScheduleService(
            semester_repository=sem_repo,
            schedule_repository=sched_repo,
            calendar_config_repository=cal_repo,
            calendar_reader=mock_reader,
        )

        tz = ZoneInfo("America/Guayaquil")
        effective = service.get_effective_schedule(
            semester_id="2026-2",
            course_code="NEURO",
            time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
            time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
        )

        mock_reader.list_events.assert_not_called()
        assert len(effective.events) > 0
        assert all(e.source == EffectiveClassSource.BASELINE for e in effective.events)

    def test_enabled_calendar_calls_google_reader_and_filters_aliases(
        self,
        setup_repos: tuple[SemesterRepository, ScheduleRepository, CalendarConfigRepository, Path],
    ) -> None:
        """Verify when calendar is enabled, events are fetched and filtered by aliases."""
        sem_repo, sched_repo, cal_repo, root = setup_repos

        # Update calendar config to enabled
        (root / "calendar" / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
enabled: true
calendar_id: "cal_active"
aliases:
  - "Neurología"
  - "NEURO"
cancellation_markers:
  - "cancelada"
""",
            encoding="utf-8",
        )

        tz = ZoneInfo("America/Guayaquil")
        cal_evt_match = OperationalCalendarEvent(
            event_id="cal_1",
            calendar_id="cal_active",
            title="Clase de Neurología",
            start=datetime(2026, 8, 4, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 4, 10, 0, tzinfo=tz),
            all_day=False,
        )
        cal_evt_other = OperationalCalendarEvent(
            event_id="cal_2",
            calendar_id="cal_active",
            title="Clase de Cardiología",  # Non-matching
            start=datetime(2026, 8, 4, 14, 0, tzinfo=tz),
            end=datetime(2026, 8, 4, 16, 0, tzinfo=tz),
            all_day=False,
        )

        mock_reader = MagicMock(spec=GoogleCalendarReader)
        mock_reader.list_events.return_value = [cal_evt_match, cal_evt_other]

        service = EffectiveScheduleService(
            semester_repository=sem_repo,
            schedule_repository=sched_repo,
            calendar_config_repository=cal_repo,
            calendar_reader=mock_reader,
        )

        effective = service.get_effective_schedule(
            semester_id="2026-2",
            course_code="NEURO",
            time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
            time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
        )

        mock_reader.list_events.assert_called_once()
        evt_aug4 = next(e for e in effective.events if e.date == datetime(2026, 8, 4).date())
        assert evt_aug4.source == EffectiveClassSource.BASELINE_AND_CALENDAR
        assert evt_aug4.calendar_event_id == "cal_1"

    def test_enabled_calendar_without_reader_raises_error(
        self,
        setup_repos: tuple[SemesterRepository, ScheduleRepository, CalendarConfigRepository, Path],
    ) -> None:
        """Verify enabled calendar without GoogleCalendarReader raises CalendarConfigError."""
        sem_repo, sched_repo, cal_repo, root = setup_repos

        (root / "calendar" / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
enabled: true
calendar_id: "cal_active"
aliases:
  - "NEURO"
""",
            encoding="utf-8",
        )

        service = EffectiveScheduleService(
            semester_repository=sem_repo,
            schedule_repository=sched_repo,
            calendar_config_repository=cal_repo,
            calendar_reader=None,  # No reader!
        )

        tz = ZoneInfo("America/Guayaquil")
        with pytest.raises(CalendarConfigError, match="no GoogleCalendarReader was provided"):
            service.get_effective_schedule(
                semester_id="2026-2",
                course_code="NEURO",
                time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
                time_max=datetime(2026, 8, 31, 0, 0, tzinfo=tz),
            )

    def test_missing_semester_propagates_not_found_error(
        self,
        setup_repos: tuple[SemesterRepository, ScheduleRepository, CalendarConfigRepository, Path],
    ) -> None:
        """Verify missing semester raises SemesterConfigNotFoundError."""
        sem_repo, sched_repo, cal_repo, _ = setup_repos
        service = EffectiveScheduleService(
            semester_repository=sem_repo,
            schedule_repository=sched_repo,
            calendar_config_repository=cal_repo,
        )

        tz = ZoneInfo("America/Guayaquil")
        with pytest.raises(SemesterConfigNotFoundError):
            service.get_effective_schedule(
                semester_id="2026-1",
                course_code="NEURO",
                time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
                time_max=datetime(2026, 8, 31, 0, 0, tzinfo=tz),
            )
