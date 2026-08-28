"""Unit tests for TeachingLogRepository."""

from datetime import date
from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    TeachingLogError,
    TeachingLogNotFoundError,
    TeachingLogValidationError,
)
from medsemiotics.domain.teaching_log import CoverageStatus
from medsemiotics.services.teaching_log_repository import TeachingLogRepository


class TestTeachingLogRepository:
    """Test suite for TeachingLogRepository filesystem operations."""

    @pytest.fixture
    def setup_logs_dir(self, tmp_path: Path) -> Path:
        """Create mock teaching logs directory."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)

        # Empty sessions log
        (sem_dir / "GASTRO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
sessions: []
""",
            encoding="utf-8",
        )

        # Populated sessions log
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
sessions:
  - session_id: "session-01"
    semester_id: "2026-2"
    course_code: "NEURO"
    session_date: "2026-08-15"
    sequence_number: 1
    notes: "First lecture"
    topics:
      - topic_id: "neuro-intro"
        status: "completed"
        notes: "Solid student engagement"
""",
            encoding="utf-8",
        )

        return root

    def test_empty_sessions_returns_empty_list(self, setup_logs_dir: Path) -> None:
        """Verify empty sessions list in YAML returns []."""
        repo = TeachingLogRepository(setup_logs_dir)
        sessions = repo.get_sessions("2026-2", "GASTRO")
        assert sessions == []

    def test_populated_sessions_load(self, setup_logs_dir: Path) -> None:
        """Verify populated sessions load correctly into TeachingSession instances."""
        repo = TeachingLogRepository(setup_logs_dir)
        sessions = repo.get_sessions("2026-2", "NEURO")

        assert len(sessions) == 1
        assert sessions[0].session_id == "session-01"
        assert sessions[0].session_date == date(2026, 8, 15)
        assert sessions[0].sequence_number == 1
        assert sessions[0].topics[0].status == CoverageStatus.COMPLETED

    def test_missing_file_raises_not_found(self, setup_logs_dir: Path) -> None:
        """Verify missing teaching log file raises TeachingLogNotFoundError."""
        repo = TeachingLogRepository(setup_logs_dir)
        with pytest.raises(TeachingLogNotFoundError, match="Teaching log file not found"):
            repo.get_sessions("2026-2", "CARDIO")

    def test_invalid_parameters_raise_validation_error(self, setup_logs_dir: Path) -> None:
        """Verify invalid semester or course parameter raises TeachingLogValidationError."""
        repo = TeachingLogRepository(setup_logs_dir)
        with pytest.raises(TeachingLogValidationError):
            repo.get_sessions("invalid-sem", "NEURO")

    def test_malformed_yaml_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify malformed YAML raises TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("sessions: [unclosed", encoding="utf-8")

        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogValidationError, match="Malformed YAML"):
            repo.get_sessions("2026-2", "NEURO")

    def test_non_dict_root_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify non-mapping root in YAML raises TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("- item1\n- item2\n", encoding="utf-8")

        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogValidationError, match="Expected YAML mapping"):
            repo.get_sessions("2026-2", "NEURO")

    def test_non_list_sessions_field_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify non-list sessions field raises TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("sessions: not_a_list\n", encoding="utf-8")

        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogValidationError, match="Invalid 'sessions' entry"):
            repo.get_sessions("2026-2", "NEURO")

    def test_invalid_session_entry_structure_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify non-dict session entries raise TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("sessions:\n  - not_a_dict\n", encoding="utf-8")

        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogValidationError, match="Invalid session entry"):
            repo.get_sessions("2026-2", "NEURO")

    def test_top_level_identifier_mismatch_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify mismatch in top-level metadata raises TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
sessions: []
""",
            encoding="utf-8",
        )

        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogValidationError, match="mismatched course_code"):
            repo.get_sessions("2026-2", "NEURO")

    def test_top_level_invalid_format_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify invalid format in top-level metadata raises TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "invalid-sem"
course_code: "NEURO"
sessions: []
""",
            encoding="utf-8",
        )

        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogValidationError):
            repo.get_sessions("2026-2", "NEURO")

    def test_invalid_session_model_validation_failure(self, tmp_path: Path) -> None:
        """Verify invalid session data raises TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
sessions:
  - session_id: "session-01"
    semester_id: "2026-2"
    course_code: "NEURO"
    session_date: "2026-08-15"
    sequence_number: 0
    topics: []
""",
            encoding="utf-8",
        )

        repo = TeachingLogRepository(root)
        with pytest.raises(
            TeachingLogValidationError, match="Validation failed for teaching session"
        ):
            repo.get_sessions("2026-2", "NEURO")

    def test_session_inner_identifier_mismatch_raises_validation_error(
        self, tmp_path: Path
    ) -> None:
        """Verify inner session mismatch raises TeachingLogValidationError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
sessions:
  - session_id: "session-01"
    semester_id: "2026-1"
    course_code: "NEURO"
    session_date: "2026-08-15"
    sequence_number: 1
    topics:
      - topic_id: "neuro-intro"
        status: "completed"
""",
            encoding="utf-8",
        )

        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogValidationError, match="mismatched identifiers"):
            repo.get_sessions("2026-2", "NEURO")

    def test_io_error_raises_teaching_log_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify OSError raises controlled TeachingLogError."""
        root = tmp_path / "teaching_logs"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("dummy", encoding="utf-8")

        def mock_read_text(*_args: object, **_kwargs: object) -> str:
            raise OSError("Disk failure")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        repo = TeachingLogRepository(root)
        with pytest.raises(TeachingLogError, match="Failed to read"):
            repo.get_sessions("2026-2", "NEURO")

    def test_root_dir_property(self, tmp_path: Path) -> None:
        """Verify root_dir property returns configured path."""
        repo = TeachingLogRepository(tmp_path)
        assert repo.root_dir == tmp_path
