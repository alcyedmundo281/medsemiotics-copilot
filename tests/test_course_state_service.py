"""Unit tests for CourseStateService orchestration."""

from pathlib import Path

import pytest

from medsemiotics.domain.academic_state import TopicProgressStatus
from medsemiotics.domain.exceptions import (
    SyllabusNotFoundError,
    TeachingLogNotFoundError,
)
from medsemiotics.services.course_state_service import CourseStateService
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_log_repository import TeachingLogRepository


class TestCourseStateService:
    """Test suite for CourseStateService orchestration."""

    @pytest.fixture
    def service_fixture(self, tmp_path: Path) -> tuple[CourseStateService, Path, Path]:
        """Create sample syllabus and teaching log repositories."""
        syllabi_dir = tmp_path / "syllabi"
        logs_dir = tmp_path / "teaching_logs"

        (syllabi_dir / "2026-2").mkdir(parents=True)
        (logs_dir / "2026-2").mkdir(parents=True)

        (syllabi_dir / "2026-2" / "NEURO.yaml").write_text(
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

        (logs_dir / "2026-2" / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
sessions:
  - session_id: "session-01"
    semester_id: "2026-2"
    course_code: "NEURO"
    session_date: "2026-08-15"
    sequence_number: 1
    topics:
      - topic_id: "neuro-intro"
        status: "completed"
      - topic_id: "extra-clinical-pearls"
        status: "introduced"
""",
            encoding="utf-8",
        )

        syllabus_repo = SyllabusRepository(syllabi_dir)
        log_repo = TeachingLogRepository(logs_dir)
        service = CourseStateService(syllabus_repo, log_repo)

        return service, syllabi_dir, logs_dir

    def test_get_state_successful_projection(
        self, service_fixture: tuple[CourseStateService, Path, Path]
    ) -> None:
        """Verify get_state retrieves and projects course academic state."""
        service, _, _ = service_fixture
        state = service.get_state("2026-2", "NEURO")

        assert state.semester_id == "2026-2"
        assert state.course_code == "NEURO"
        assert len(state.topics) == 2

        intro = next(t for t in state.topics if t.topic_id == "neuro-intro")
        assert intro.status == TopicProgressStatus.COMPLETED
        assert intro.session_count == 1

        mental = next(t for t in state.topics if t.topic_id == "mental-status")
        assert mental.status == TopicProgressStatus.NOT_STARTED

        assert state.completion_ratio == 0.5
        assert state.next_required_topic is not None
        assert state.next_required_topic.topic_id == "mental-status"

    def test_get_unplanned_taught_topic_ids(
        self, service_fixture: tuple[CourseStateService, Path, Path]
    ) -> None:
        """Verify get_unplanned_taught_topic_ids identifies extra topics."""
        service, _, _ = service_fixture
        unplanned = service.get_unplanned_taught_topic_ids("2026-2", "NEURO")
        assert unplanned == ["extra-clinical-pearls"]

    def test_missing_syllabus_raises_project_exception(
        self, service_fixture: tuple[CourseStateService, Path, Path]
    ) -> None:
        """Verify requesting non-existent course raises SyllabusNotFoundError."""
        service, _, _ = service_fixture
        with pytest.raises(SyllabusNotFoundError):
            service.get_state("2026-2", "CARDIO")

    def test_missing_teaching_log_raises_project_exception(
        self, tmp_path: Path
    ) -> None:
        """Verify missing teaching log raises TeachingLogNotFoundError."""
        syllabi_dir = tmp_path / "syllabi"
        logs_dir = tmp_path / "teaching_logs"

        (syllabi_dir / "2026-2").mkdir(parents=True)
        (logs_dir / "2026-2").mkdir(parents=True)

        (syllabi_dir / "2026-2" / "GASTRO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
topics:
  - topic_id: "gastro-intro"
    planned_order: 1
    required: true
""",
            encoding="utf-8",
        )

        # GASTRO log does not exist
        syllabus_repo = SyllabusRepository(syllabi_dir)
        log_repo = TeachingLogRepository(logs_dir)
        service = CourseStateService(syllabus_repo, log_repo)

        with pytest.raises(TeachingLogNotFoundError):
            service.get_state("2026-2", "GASTRO")
