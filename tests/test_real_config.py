"""Integration tests verifying the actual project configuration files on disk."""

import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
import yaml

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.domain.academic_state import TopicProgressStatus
from medsemiotics.domain.schedule import ClassWeekday
from medsemiotics.domain.teaching_coach import TeachingCoachPreviewRequest
from medsemiotics.domain.teaching_log import CoverageStatus
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_ROOT = PROJECT_ROOT / "config"
SEMESTER_ID = "2026-2"

# The official syllabi are the single source of truth for what is taught and when. These tests
# assert that the tracked engine configuration is a faithful projection of them, so updating the
# teaching content never requires editing expectations here.
OFFICIAL_SYLLABI = {
    "NEURO": "silabo_neurologia_v2.yaml",
    "GASTRO": "silabo_gastroenterologia_v2.yaml",
}


def official_weeks(course_code: str) -> list[dict[str, object]]:
    """Load the official syllabus weeks for a course, ordered by week number."""
    path = CONFIG_ROOT / "syllabi" / SEMESTER_ID / OFFICIAL_SYLLABI[course_code]
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return sorted(data["schedule_18_weeks"], key=lambda week: int(week["week"]))


def official_course_info(course_code: str) -> dict[str, object]:
    """Load the official course_info block for a course."""
    path = CONFIG_ROOT / "syllabi" / SEMESTER_ID / OFFICIAL_SYLLABI[course_code]
    return dict(yaml.safe_load(path.read_text(encoding="utf-8"))["course_info"])


def delivered_weeks(course_code: str) -> list[dict[str, object]]:
    """Return the official weeks already reported as delivered."""
    return [week for week in official_weeks(course_code) if week["status"] == "completed"]


def next_official_week(course_code: str) -> dict[str, object]:
    """Return the first official week that has not been delivered yet."""
    pending = [week for week in official_weeks(course_code) if week["status"] != "completed"]
    assert pending, f"The official {course_code} syllabus reports no pending week."
    return pending[0]


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


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_real_syllabi_2026_2(course_code: str) -> None:
    """Verify each tracked plan mirrors the topic order of its official syllabus."""
    plan = SyllabusRepository(CONFIG_ROOT / "syllabi").get(SEMESTER_ID, course_code)

    assert plan.semester_id == SEMESTER_ID
    assert plan.course_code == course_code

    weeks = official_weeks(course_code)
    assert [topic.topic_id for topic in plan.ordered_topics] == [week["topic_id"] for week in weeks]
    assert [topic.planned_week for topic in plan.ordered_topics] == [
        int(week["week"]) for week in weeks
    ]


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_real_teaching_logs_2026_2(course_code: str) -> None:
    """Verify the tracked log holds exactly the weeks the official syllabus reports as delivered."""
    sessions = TeachingLogRepository(CONFIG_ROOT / "teaching_logs").get_sessions(
        SEMESTER_ID, course_code
    )
    delivered = delivered_weeks(course_code)

    assert len(sessions) == len(delivered)
    for session, week in zip(sessions, delivered, strict=True):
        assert session.session_date == date.fromisoformat(str(week["date"]))
        assert [topic.topic_id for topic in session.topics] == [week["topic_id"]]
        assert all(topic.status == CoverageStatus.COMPLETED for topic in session.topics)

    # A week still marked active or projected must never appear as taught.
    logged_topics = {topic.topic_id for session in sessions for topic in session.topics}
    assert next_official_week(course_code)["topic_id"] not in logged_topics


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_real_academic_state_2026_2(course_code: str) -> None:
    """Verify the projected state proposes the first week that has not been taught yet."""
    service = CourseStateService(
        SyllabusRepository(CONFIG_ROOT / "syllabi"),
        TeachingLogRepository(CONFIG_ROOT / "teaching_logs"),
    )

    state = service.get_state(SEMESTER_ID, course_code)
    weeks = official_weeks(course_code)
    delivered = delivered_weeks(course_code)

    assert len(state.topics) == len(weeks)
    completed = [t for t in state.topics if t.status == TopicProgressStatus.COMPLETED]
    assert len(completed) == len(delivered)
    assert state.next_required_topic is not None
    assert state.next_required_topic.topic_id == next_official_week(course_code)["topic_id"]

    assert service.get_unplanned_taught_topic_ids(SEMESTER_ID, course_code) == []


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_real_schedules_are_enabled(course_code: str) -> None:
    """Verify the date-only baseline covers the official term on the official weekday."""
    schedule = ScheduleRepository(CONFIG_ROOT / "schedules").get(SEMESTER_ID, course_code)
    info = official_course_info(course_code)
    start = date.fromisoformat(str(info["start_date"]))
    end = date.fromisoformat(str(info["end_date"]))

    assert schedule.enabled is True
    assert schedule.teaching_start_date == start
    assert schedule.teaching_end_date == end
    assert [rule.weekday for rule in schedule.meeting_rules] == [ClassWeekday.from_date(start)]

    for week in official_weeks(course_code):
        assert schedule.is_class_date(date.fromisoformat(str(week["date"]))) is True
    assert schedule.is_class_date(start + timedelta(days=1)) is False


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


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_real_teaching_guides_2026_2(course_code: str) -> None:
    """Verify no curated guide points at a topic the course no longer teaches."""
    repository = TeachingGuideRepository(CONFIG_ROOT / "teaching_guides")
    syllabus = SyllabusRepository(CONFIG_ROOT / "syllabi").get(SEMESTER_ID, course_code)

    catalog = repository.get_catalog(SEMESTER_ID, course_code)
    syllabus_topics = {topic.topic_id for topic in syllabus.topics}

    assert catalog.enabled is True
    assert catalog.guides
    assert {guide.topic_id for guide in catalog.guides} <= syllabus_topics


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_every_pending_week_has_a_curated_guide(course_code: str) -> None:
    """Verify every class still ahead can be briefed, not only the next one.

    The Teaching Coach refuses to draft for a topic with no curated guide. When this fails, the
    fix is to curate the guides for the topics named in the failure, not to relax the assertion.
    """
    repository = TeachingGuideRepository(CONFIG_ROOT / "teaching_guides")
    catalog = repository.get_catalog(SEMESTER_ID, course_code)
    curated = {guide.topic_id for guide in catalog.guides}

    pending = [
        str(week["topic_id"])
        for week in official_weeks(course_code)
        if week["status"] != "completed"
    ]

    assert pending, f"The official {course_code} syllabus reports no pending week."
    assert [topic_id for topic_id in pending if topic_id not in curated] == []


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_next_topic_of_each_course_has_a_curated_guide(course_code: str) -> None:
    """Verify the upcoming class can be briefed.

    The Teaching Coach refuses to draft for a topic with no curated guide. When this fails, the
    fix is to curate the guide for the topic named in the failure, not to relax the assertion.
    """
    repository = TeachingGuideRepository(CONFIG_ROOT / "teaching_guides")
    topic_id = str(next_official_week(course_code)["topic_id"])

    guide = repository.get_guide(SEMESTER_ID, course_code, topic_id)

    assert guide.topic_id == topic_id
    assert guide.topic_title


def test_real_effective_schedule_uses_active_baseline_without_calendar_events() -> None:
    """Verify empty calendars do not erase the active institutional baseline."""
    calendar_reader = MagicMock()
    calendar_reader.list_events.return_value = []
    service = EffectiveScheduleService(
        SemesterRepository(CONFIG_ROOT / "semesters"),
        ScheduleRepository(CONFIG_ROOT / "schedules"),
        CalendarConfigRepository(CONFIG_ROOT / "calendar"),
        calendar_reader=calendar_reader,
    )

    tz = ZoneInfo("America/Guayaquil")
    for course_code in ("NEURO", "GASTRO"):
        weeks = official_weeks(course_code)
        first = date.fromisoformat(str(weeks[0]["date"]))
        last = date.fromisoformat(str(weeks[-1]["date"]))
        class_dates = service.get_class_dates(
            semester_id=SEMESTER_ID,
            course_code=course_code,
            time_min=datetime(first.year, first.month, first.day, 0, 0, tzinfo=tz),
            time_max=datetime(first.year, first.month, first.day, 23, 59, tzinfo=tz),
        )
        assert class_dates[0] == first
        assert class_dates[-1] == last
        assert [date.fromisoformat(str(week["date"])) for week in weeks] == class_dates

    assert calendar_reader.list_events.call_count == 2


@pytest.mark.parametrize("course_code", ["NEURO", "GASTRO"])
def test_real_teaching_coach_preview_covers_neuro_and_gastro(course_code: str) -> None:
    """Verify a one-call preview drafts the next untaught topic for each active course."""
    calendar_reader = MagicMock()
    calendar_reader.list_events.return_value = []

    semester_repository = SemesterRepository(CONFIG_ROOT / "semesters")
    schedule_repository = ScheduleRepository(CONFIG_ROOT / "schedules")
    calendar_repository = CalendarConfigRepository(CONFIG_ROOT / "calendar")
    syllabus_repository = SyllabusRepository(CONFIG_ROOT / "syllabi")
    teaching_log_repository = TeachingLogRepository(CONFIG_ROOT / "teaching_logs")
    teaching_guide_repository = TeachingGuideRepository(CONFIG_ROOT / "teaching_guides")
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

    pending = next_official_week(course_code)
    class_date = date.fromisoformat(str(pending["date"]))
    result = preview_service.preview_class_brief(
        TeachingCoachPreviewRequest(
            semester_id=SEMESTER_ID,
            course_code=course_code,
            class_date=class_date,
            time_min=datetime.combine(class_date, datetime.min.time(), tzinfo=timezone),
            time_max=datetime.combine(class_date, datetime.max.time(), tzinfo=timezone),
            requested_by="course-director",
        )
    )

    assert result.draft.brief.topic_id == pending["topic_id"]
    assert result.draft.capability_decision.allowed is True

    # Topic discovery and agent revalidation each read the operational schedule once.
    assert calendar_reader.list_events.call_count == 2


def test_tracked_config_is_derived_from_the_official_syllabi() -> None:
    """Verify nobody hand-edited a generated file out of step with the official syllabi."""
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "sync_syllabus_v2_to_config.py"),
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
