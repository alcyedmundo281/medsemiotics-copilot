"""Integration tests verifying the actual project configuration files on disk."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.domain.academic_state import TopicProgressStatus
from medsemiotics.domain.exceptions import TeachingGuideDisabledError
from medsemiotics.domain.teaching_coach import TeachingCoachPreviewRequest
from medsemiotics.services.calendar_config_repository import (
    CalendarConfigRepository,
)
from medsemiotics.services.course_state_service import CourseStateService
from medsemiotics.services.curated_teaching_coach import CuratedTeachingCoachService
from medsemiotics.services.effective_schedule_service import (
    EffectiveScheduleService,
)
from medsemiotics.services.effective_teaching_day_service import EffectiveTeachingDayService
from medsemiotics.services.schedule_repository import ScheduleRepository
from medsemiotics.services.semester_config import (
    load_current_semester_id,
    load_semester_config,
)
from medsemiotics.services.semester_repository import SemesterRepository
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_coach_preview import TeachingCoachPreviewService
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository
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
    """Verify the tracked plans: five semiology topics for NEURO, ten clinical ones for GASTRO."""
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
    assert len(gastro_plan.topics) == 10
    assert gastro_plan.topics[0].topic_id == "fundamentos-gastroenterologia"
    assert gastro_plan.topics[-1].topic_id == "sindrome-intestino-irritable"


def test_real_teaching_logs_2026_2() -> None:
    """Verify NEURO has taught nothing yet and GASTRO carries its reconstructed first half."""
    project_root = Path(__file__).resolve().parent.parent
    logs_dir = project_root / "config" / "teaching_logs"

    repo = TeachingLogRepository(logs_dir)

    neuro_sessions = repo.get_sessions("2026-2", "NEURO")
    assert neuro_sessions == []

    gastro_sessions = repo.get_sessions("2026-2", "GASTRO")
    assert len(gastro_sessions) == 4
    assert sum(len(session.topics) for session in gastro_sessions) == 10
    assert gastro_sessions[0].session_date == date(2026, 8, 5)
    assert gastro_sessions[-1].session_date == date(2026, 8, 26)
    for session in gastro_sessions:
        assert session.notes is not None
        assert "reconstructed" in session.notes


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
    assert len(state.topics) == 10
    assert all(t.status == TopicProgressStatus.COMPLETED for t in state.topics)
    assert state.completion_ratio == 1.0
    assert state.next_required_topic is None

    unplanned = service.get_unplanned_taught_topic_ids("2026-2", "GASTRO")
    assert unplanned == []


def test_real_schedules_are_enabled() -> None:
    """Verify the active date-only baseline for both teaching courses."""
    project_root = Path(__file__).resolve().parent.parent
    sched_dir = project_root / "config" / "schedules"
    repository = ScheduleRepository(sched_dir)

    neuro = repository.get("2026-2", "NEURO")
    assert neuro.enabled is True
    assert neuro.is_class_date(date(2026, 8, 4)) is True
    assert neuro.is_class_date(date(2026, 8, 5)) is False

    gastro = repository.get("2026-2", "GASTRO")
    assert gastro.enabled is True
    assert gastro.is_class_date(date(2026, 8, 5)) is True
    assert gastro.is_class_date(date(2026, 8, 3)) is False
    assert gastro.is_class_date(date(2026, 8, 4)) is False


def test_real_calendar_config_2026_2() -> None:
    """Verify NEURO and GASTRO are bound to their dedicated Workspace calendars."""
    project_root = Path(__file__).resolve().parent.parent
    calendar_dir = project_root / "config" / "calendar"

    repo = CalendarConfigRepository(calendar_dir)

    neuro_cfg = repo.get("2026-2", "NEURO")
    assert neuro_cfg.semester_id == "2026-2"
    assert neuro_cfg.course_code == "NEURO"
    assert neuro_cfg.enabled is True
    assert neuro_cfg.calendar_id == "c_classroom6164396f@group.calendar.google.com"
    assert "Neurología" in neuro_cfg.aliases

    gastro_cfg = repo.get("2026-2", "GASTRO")
    assert gastro_cfg.semester_id == "2026-2"
    assert gastro_cfg.course_code == "GASTRO"
    assert gastro_cfg.enabled is True
    assert gastro_cfg.calendar_id == "c_classroom7c5dba86@group.calendar.google.com"
    assert "Gastroenterología" in gastro_cfg.aliases


def test_real_teaching_guides_2026_2() -> None:
    """Verify an enabled catalog covers its syllabus, and a disabled one drafts nothing."""
    project_root = Path(__file__).resolve().parent.parent
    repository = TeachingGuideRepository(project_root / "config" / "teaching_guides")
    syllabus_repository = SyllabusRepository(project_root / "config" / "syllabi")

    neuro_catalog = repository.get_catalog("2026-2", "NEURO")
    neuro_syllabus = syllabus_repository.get("2026-2", "NEURO")
    assert neuro_catalog.enabled is True
    assert len(neuro_catalog.guides) == 5
    assert {guide.topic_id for guide in neuro_catalog.guides} == {
        topic.topic_id for topic in neuro_syllabus.topics
    }
    assert repository.get_guide("2026-2", "NEURO", "neuro-intro").topic_title

    # GASTRO moved to a clinical syllabus its curated catalog does not cover yet. A disabled
    # catalog makes the Teaching Coach refuse rather than draft from stale guidance.
    gastro_catalog = repository.get_catalog("2026-2", "GASTRO")
    assert gastro_catalog.enabled is False
    assert gastro_catalog.guides == []
    with pytest.raises(TeachingGuideDisabledError):
        repository.get_guide("2026-2", "GASTRO", "fundamentos-gastroenterologia")


def test_real_effective_schedule_uses_active_baseline_without_calendar_events() -> None:
    """Verify empty calendars do not erase the active institutional baseline."""
    project_root = Path(__file__).resolve().parent.parent
    sem_dir = project_root / "config" / "semesters"
    sched_dir = project_root / "config" / "schedules"
    cal_dir = project_root / "config" / "calendar"

    calendar_reader = MagicMock()
    calendar_reader.list_events.return_value = []
    service = EffectiveScheduleService(
        SemesterRepository(sem_dir),
        ScheduleRepository(sched_dir),
        CalendarConfigRepository(cal_dir),
        calendar_reader=calendar_reader,
    )

    tz = ZoneInfo("America/Guayaquil")
    neuro_dates = service.get_class_dates(
        semester_id="2026-2",
        course_code="NEURO",
        time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
        time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
    )
    assert neuro_dates[0] == date(2026, 8, 4)
    assert date(2026, 8, 27) in neuro_dates
    assert neuro_dates[-1] == date(2026, 12, 15)

    gastro_dates = service.get_class_dates(
        semester_id="2026-2",
        course_code="GASTRO",
        time_min=datetime(2026, 8, 1, 0, 0, tzinfo=tz),
        time_max=datetime(2026, 8, 31, 23, 59, tzinfo=tz),
    )
    assert gastro_dates[0] == date(2026, 8, 5)
    assert date(2026, 8, 26) in gastro_dates
    assert gastro_dates[-1] == date(2026, 12, 9)
    assert calendar_reader.list_events.call_count == 2


def test_real_teaching_coach_preview_covers_neuro_and_gastro() -> None:
    """Verify one-call previews select curated topics for both active teaching courses."""
    project_root = Path(__file__).resolve().parent.parent
    config_root = project_root / "config"
    calendar_reader = MagicMock()
    calendar_reader.list_events.return_value = []

    semester_repository = SemesterRepository(config_root / "semesters")
    schedule_repository = ScheduleRepository(config_root / "schedules")
    calendar_repository = CalendarConfigRepository(config_root / "calendar")
    syllabus_repository = SyllabusRepository(config_root / "syllabi")
    teaching_log_repository = TeachingLogRepository(config_root / "teaching_logs")
    teaching_guide_repository = TeachingGuideRepository(config_root / "teaching_guides")
    effective_schedule_service = EffectiveScheduleService(
        semester_repository,
        schedule_repository,
        calendar_repository,
        calendar_reader=calendar_reader,
    )
    teaching_day_service = EffectiveTeachingDayService(
        effective_schedule_service,
        syllabus_repository,
        teaching_log_repository,
    )
    agent = TeachingCoachAgent(
        capability_framework=build_default_agent_framework(),
        teaching_day_service=teaching_day_service,
        course_state_service=CourseStateService(
            syllabus_repository,
            teaching_log_repository,
        ),
    )
    preview_service = TeachingCoachPreviewService(
        teaching_day_service=teaching_day_service,
        curated_teaching_coach_service=CuratedTeachingCoachService(
            teaching_guide_repository,
            agent,
        ),
    )
    timezone = ZoneInfo("America/Guayaquil")

    class_date = date(2026, 8, 4)
    result = preview_service.preview_class_brief(
        TeachingCoachPreviewRequest(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=class_date,
            time_min=datetime.combine(class_date, datetime.min.time(), tzinfo=timezone),
            time_max=datetime.combine(class_date, datetime.max.time(), tzinfo=timezone),
            requested_by="course-director",
        )
    )
    assert result.draft.brief.topic_id == "neuro-intro"
    assert result.preview_title == "NEURO — Introducción a la semiología neurológica"
    assert result.draft.capability_decision.allowed is True

    # Topic discovery and agent revalidation each read the operational schedule once.
    assert calendar_reader.list_events.call_count == 2

    # GASTRO refuses rather than drafting from a catalog that no longer covers its syllabus.
    gastro_date = date(2026, 8, 12)
    with pytest.raises(TeachingGuideDisabledError):
        preview_service.preview_class_brief(
            TeachingCoachPreviewRequest(
                semester_id="2026-2",
                course_code="GASTRO",
                class_date=gastro_date,
                time_min=datetime.combine(gastro_date, datetime.min.time(), tzinfo=timezone),
                time_max=datetime.combine(gastro_date, datetime.max.time(), tzinfo=timezone),
                requested_by="course-director",
            )
        )
