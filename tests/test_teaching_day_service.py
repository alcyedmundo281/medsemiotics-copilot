"""Unit tests for TeachingDayService orchestration."""

from datetime import date
from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    ScheduleNotFoundError,
    SyllabusNotFoundError,
    TeachingLogNotFoundError,
)
from medsemiotics.domain.teaching_position import TeachingPaceStatus
from medsemiotics.services.schedule_repository import ScheduleRepository
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_day_service import TeachingDayService
from medsemiotics.services.teaching_log_repository import TeachingLogRepository


class TestTeachingDayService:
    """Test suite for TeachingDayService multi-repository orchestration."""

    @pytest.fixture
    def day_service_fixture(self, tmp_path: Path) -> tuple[TeachingDayService, Path, Path, Path]:
        """Create sample schedule, syllabus, and teaching log repository fixtures."""
        sched_dir = tmp_path / "schedules"
        syll_dir = tmp_path / "syllabi"
        log_dir = tmp_path / "teaching_logs"

        (sched_dir / "2026-2").mkdir(parents=True)
        (syll_dir / "2026-2").mkdir(parents=True)
        (log_dir / "2026-2").mkdir(parents=True)

        (sched_dir / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
enabled: true
teaching_start_date: "2026-08-01"
teaching_end_date: "2026-08-31"
meeting_rules:
  - weekday: "tuesday"
  - weekday: "thursday"
exceptions: []
""",
            encoding="utf-8",
        )

        (syll_dir / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
topics:
  - topic_id: "neuro-intro"
    planned_order: 1
    required: true
  - topic_id: "mental-status"
    planned_order: 2
    required: true
""",
            encoding="utf-8",
        )

        (log_dir / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
sessions:
  - session_id: "s1"
    semester_id: "2026-2"
    course_code: "NEURO"
    session_date: "2026-08-04"
    sequence_number: 1
    topics:
      - topic_id: "neuro-intro"
        status: "completed"
""",
            encoding="utf-8",
        )

        sched_repo = ScheduleRepository(sched_dir)
        syll_repo = SyllabusRepository(syll_dir)
        log_repo = TeachingLogRepository(log_dir)

        service = TeachingDayService(sched_repo, syll_repo, log_repo)
        return service, sched_dir, syll_dir, log_dir

    def test_get_position_and_topic_for_date(
        self, day_service_fixture: tuple[TeachingDayService, Path, Path, Path]
    ) -> None:
        """Verify get_position and get_topic_for_date return consistent outputs."""
        service, _, _, _ = day_service_fixture

        # Evaluate on Aug 6, 2026 (Thursday, session 2)
        pos = service.get_position("2026-2", "NEURO", date(2026, 8, 6))
        assert pos.is_class_date is True
        assert pos.expected_session_count == 2
        assert pos.actual_session_count == 1
        assert pos.current_topic_id == "mental-status"
        assert pos.pace_status == TeachingPaceStatus.ON_TRACK

        topic_id = service.get_topic_for_date("2026-2", "NEURO", date(2026, 8, 6))
        assert topic_id == "mental-status"

    def test_missing_schedule_raises_exception(
        self, day_service_fixture: tuple[TeachingDayService, Path, Path, Path]
    ) -> None:
        """Verify missing schedule raises ScheduleNotFoundError."""
        service, _, _, _ = day_service_fixture
        with pytest.raises(ScheduleNotFoundError):
            service.get_position("2026-2", "CARDIO", date(2026, 8, 6))

    def test_missing_syllabus_raises_exception(self, tmp_path: Path) -> None:
        """Verify missing syllabus raises SyllabusNotFoundError."""
        sched_dir = tmp_path / "schedules"
        syll_dir = tmp_path / "syllabi"
        log_dir = tmp_path / "teaching_logs"

        (sched_dir / "2026-2").mkdir(parents=True)
        (syll_dir / "2026-2").mkdir(parents=True)
        (log_dir / "2026-2").mkdir(parents=True)

        (sched_dir / "2026-2" / "GASTRO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
enabled: true
teaching_start_date: "2026-08-01"
teaching_end_date: "2026-08-31"
meeting_rules:
  - weekday: "monday"
""",
            encoding="utf-8",
        )
        (log_dir / "2026-2" / "GASTRO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
sessions: []
""",
            encoding="utf-8",
        )

        service = TeachingDayService(
            ScheduleRepository(sched_dir),
            SyllabusRepository(syll_dir),
            TeachingLogRepository(log_dir),
        )

        with pytest.raises(SyllabusNotFoundError):
            service.get_position("2026-2", "GASTRO", date(2026, 8, 6))

    def test_missing_teaching_log_raises_exception(self, tmp_path: Path) -> None:
        """Verify missing log raises TeachingLogNotFoundError."""
        sched_dir = tmp_path / "schedules"
        syll_dir = tmp_path / "syllabi"
        log_dir = tmp_path / "teaching_logs"

        (sched_dir / "2026-2").mkdir(parents=True)
        (syll_dir / "2026-2").mkdir(parents=True)
        (log_dir / "2026-2").mkdir(parents=True)

        (sched_dir / "2026-2" / "GASTRO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
enabled: true
teaching_start_date: "2026-08-01"
teaching_end_date: "2026-08-31"
meeting_rules:
  - weekday: "monday"
""",
            encoding="utf-8",
        )
        (syll_dir / "2026-2" / "GASTRO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
topics:
  - topic_id: "gastro-intro"
    planned_order: 1
""",
            encoding="utf-8",
        )

        service = TeachingDayService(
            ScheduleRepository(sched_dir),
            SyllabusRepository(syll_dir),
            TeachingLogRepository(log_dir),
        )

        with pytest.raises(TeachingLogNotFoundError):
            service.get_position("2026-2", "GASTRO", date(2026, 8, 6))
