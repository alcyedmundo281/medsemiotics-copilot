"""Integration tests verifying the actual project configuration files on disk."""

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from medsemiotics.domain.academic_state import TopicProgressStatus
from medsemiotics.domain.teaching_position import TeachingPaceStatus
from medsemiotics.services.calendar_config_repository import (
    CalendarConfigRepository,
)
from medsemiotics.services.course_state_service import CourseStateService
from medsemiotics.services.effective_schedule_service import (
    EffectiveScheduleService,
)
from medsemiotics.services.schedule_repository import ScheduleRepository
from medsemiotics.services.semester_config import (
    load_current_semester_id,
    load_semester_config,
)
from medsemiotics.services.semester_repository import SemesterRepository
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_day_service import TeachingDayService
from medsemiotics.services.teaching_log_repository import TeachingLogRepository


def test_real_semester_2026_2_config() -> None:
    """Verify config/semesters/2026-2.yaml contains valid semester configuration."""
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "config" / "semesters" / "2026-2.yaml"

    assert config_path.is_file(), f"Expected config file at {config_path}"

    config = load_semester_config(config_path)

    assert config.semester_id == "2026-2"
    assert config.display_name == "2026-2"
    assert config.active is True
    assert config.timezone == "America/Guayaquil"
    assert config.tz.key == "America/Guayaquil"

    course_codes = {course.code for course in config.courses}
    assert course_codes == {"NEURO", "GASTRO"}

    course_map = {course.code: course for course in config.courses}
    assert course_map["NEURO"].name == "Neurología"
    assert course_map["NEURO"].active is True
    assert course_map["GASTRO"].name == "Gastroenterología"
    assert course_map["GASTRO"].active is True


def test_real_current_semester_pointer() -> None:
    """Verify config/current_semester.yaml points to an active valid semester."""
    project_root = Path(__file__).resolve().parent.parent
    pointer_path = project_root / "config" / "current_semester.yaml"

    assert pointer_path.is_file(), f"Expected pointer file at {pointer_path}"

    current_id = load_current_semester_id(pointer_path)
    assert current_id == "2026-2"


def test_real_repository_resolution() -> None:
    """Verify SemesterRepository resolves real config directory properly."""
    project_root = Path(__file__).resolve().parent.parent
    semesters_dir = project_root / "config" / "semesters"

    repo = SemesterRepository(semesters_dir)
    assert repo.exists("2026-2") is True
    assert "2026-2" in repo.list_semesters()

    config = repo.get("2026-2")
    assert config.semester_id == "2026-2"
    assert config.timezone == "America/Guayaquil"


def test_real_syllabi_2026_2() -> None:
    """Verify config/syllabi/2026-2 NEURO and GASTRO have exactly 5 planned topics each."""
    project_root = Path(__file__).resolve().parent.parent
    syllabi_dir = project_root / "config" / "syllabi"

    repo = SyllabusRepository(syllabi_dir)

    neuro_plan = repo.get("2026-2", "NEURO")
    assert neuro_plan.semester_id == "2026-2"
    assert neuro_plan.course_code == "NEURO"
    assert len(neuro_plan.topics) == 5

    gastro_plan = repo.get("2026-2", "GASTRO")
    assert gastro_plan.semester_id == "2026-2"
    assert gastro_plan.course_code == "GASTRO"
    assert len(gastro_plan.topics) == 5


def test_real_teaching_logs_2026_2() -> None:
    """Verify config/teaching_logs/2026-2 NEURO and GASTRO files exist and have empty sessions."""
    project_root = Path(__file__).resolve().parent.parent
    logs_dir = project_root / "config" / "teaching_logs"

    repo = TeachingLogRepository(logs_dir)

    neuro_sessions = repo.get_sessions("2026-2", "NEURO")
    assert neuro_sessions == []

    gastro_sessions = repo.get_sessions("2026-2", "GASTRO")
    assert gastro_sessions == []


def test_real_academic_state_neuro_2026_2() -> None:
    """Verify NEURO academic state projection against real configuration."""
    project_root = Path(__file__).resolve().parent.parent
    syllabi_dir = project_root / "config" / "syllabi"
    logs_dir = project_root / "config" / "teaching_logs"

    service = CourseStateService(
        SyllabusRepository(syllabi_dir),
        TeachingLogRepository(logs_dir),
    )

    state = service.get_state("2026-2", "NEURO")
    assert len(state.topics) == 5
    assert all(t.status == TopicProgressStatus.NOT_STARTED for t in state.topics)
    assert state.completion_ratio == 0.0
    assert state.next_required_topic is not None
    assert state.next_required_topic.planned_order == 1

    unplanned = service.get_unplanned_taught_topic_ids("2026-2", "NEURO")
    assert unplanned == []


def test_real_academic_state_gastro_2026_2() -> None:
    """Verify GASTRO academic state projection against real configuration."""
    project_root = Path(__file__).resolve().parent.parent
    syllabi_dir = project_root / "config" / "syllabi"
    logs_dir = project_root / "config" / "teaching_logs"

    service = CourseStateService(
        SyllabusRepository(syllabi_dir),
        TeachingLogRepository(logs_dir),
    )

    state = service.get_state("2026-2", "GASTRO")
    assert len(state.topics) == 5
    assert all(t.status == TopicProgressStatus.NOT_STARTED for t in state.topics)
    assert state.completion_ratio == 0.0
    assert state.next_required_topic is not None
    assert state.next_required_topic.planned_order == 1

    unplanned = service.get_unplanned_taught_topic_ids("2026-2", "GASTRO")
    assert unplanned == []


def test_real_teaching_position_disabled_schedules() -> None:
    """Verify real placeholder schedule files resolve to UNAVAILABLE."""
    project_root = Path(__file__).resolve().parent.parent
    sched_dir = project_root / "config" / "schedules"
    syll_dir = project_root / "config" / "syllabi"
    log_dir = project_root / "config" / "teaching_logs"

    service = TeachingDayService(
        ScheduleRepository(sched_dir),
        SyllabusRepository(syll_dir),
        TeachingLogRepository(log_dir),
    )

    neuro_pos = service.get_position("2026-2", "NEURO", date(2026, 8, 15))
    assert neuro_pos.pace_status == TeachingPaceStatus.UNAVAILABLE
    assert service.get_topic_for_date("2026-2", "NEURO", date(2026, 8, 15)) is None

    gastro_pos = service.get_position("2026-2", "GASTRO", date(2026, 8, 15))
    assert gastro_pos.pace_status == TeachingPaceStatus.UNAVAILABLE
    assert service.get_topic_for_date("2026-2", "GASTRO", date(2026, 8, 15)) is None


def test_real_calendar_config_2026_2() -> None:
    """Verify real calendar config files for NEURO and GASTRO exist with enabled: false."""
    project_root = Path(__file__).resolve().parent.parent
    calendar_dir = project_root / "config" / "calendar"

    repo = CalendarConfigRepository(calendar_dir)

    neuro_cfg = repo.get("2026-2", "NEURO")
    assert neuro_cfg.semester_id == "2026-2"
    assert neuro_cfg.course_code == "NEURO"
    assert neuro_cfg.enabled is False
    assert neuro_cfg.calendar_id is None
    assert "Neurología" in neuro_cfg.aliases

    gastro_cfg = repo.get("2026-2", "GASTRO")
    assert gastro_cfg.semester_id == "2026-2"
    assert gastro_cfg.course_code == "GASTRO"
    assert gastro_cfg.enabled is False
    assert gastro_cfg.calendar_id is None
    assert "Gastroenterología" in gastro_cfg.aliases


def test_real_effective_schedule_empty() -> None:
    """Verify that with real placeholder configs (both disabled), effective schedule has no active class dates."""
    project_root = Path(__file__).resolve().parent.parent
    sem_dir = project_root / "config" / "semesters"
    sched_dir = project_root / "config" / "schedules"
    cal_dir = project_root / "config" / "calendar"

    service = EffectiveScheduleService(
        SemesterRepository(sem_dir),
        ScheduleRepository(sched_dir),
        CalendarConfigRepository(cal_dir),
    )

    tz = ZoneInfo("America/Guayaquil")
    neuro_dates = service.get_class_dates(
        semester_id="2026-2",
        course_code="NEURO",
        time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
        time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
    )
    assert neuro_dates == []

    gastro_dates = service.get_class_dates(
        semester_id="2026-2",
        course_code="GASTRO",
        time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
        time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
    )
    assert gastro_dates == []
