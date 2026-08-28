"""Unit tests for ScheduleRepository."""

from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    ScheduleError,
    ScheduleNotFoundError,
    ScheduleValidationError,
)
from medsemiotics.services.schedule_repository import ScheduleRepository


class TestScheduleRepository:
    """Test suite for ScheduleRepository filesystem operations."""

    @pytest.fixture
    def setup_schedule_dir(self, tmp_path: Path) -> Path:
        """Create mock schedule directory."""
        root = tmp_path / "schedules"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)

        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
enabled: true
teaching_start_date: "2026-08-01"
teaching_end_date: "2026-12-15"
meeting_rules:
  - weekday: "tuesday"
  - weekday: "thursday"
exceptions: []
""",
            encoding="utf-8",
        )

        return root

    def test_valid_get(self, setup_schedule_dir: Path) -> None:
        """Verify loading an existing valid schedule."""
        repo = ScheduleRepository(setup_schedule_dir)
        schedule = repo.get("2026-2", "NEURO")

        assert schedule.semester_id == "2026-2"
        assert schedule.course_code == "NEURO"
        assert schedule.enabled is True
        assert len(schedule.meeting_rules) == 2

    def test_missing_file_raises_not_found(self, setup_schedule_dir: Path) -> None:
        """Verify missing schedule file raises ScheduleNotFoundError."""
        repo = ScheduleRepository(setup_schedule_dir)
        with pytest.raises(ScheduleNotFoundError, match="Schedule file not found"):
            repo.get("2026-2", "GASTRO")

    def test_invalid_parameters_raise_validation_error(self, setup_schedule_dir: Path) -> None:
        """Verify invalid semester or course parameter raises ScheduleValidationError."""
        repo = ScheduleRepository(setup_schedule_dir)
        with pytest.raises(ScheduleValidationError):
            repo.get("invalid-sem", "NEURO")

    def test_malformed_yaml_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify malformed YAML raises ScheduleValidationError."""
        root = tmp_path / "schedules"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("semester_id: [unclosed", encoding="utf-8")

        repo = ScheduleRepository(root)
        with pytest.raises(ScheduleValidationError, match="Malformed YAML"):
            repo.get("2026-2", "NEURO")

    def test_non_dict_root_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify non-mapping root raises ScheduleValidationError."""
        root = tmp_path / "schedules"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("- item1\n- item2\n", encoding="utf-8")

        repo = ScheduleRepository(root)
        with pytest.raises(ScheduleValidationError, match="Expected YAML mapping"):
            repo.get("2026-2", "NEURO")

    def test_mismatched_internal_identifiers_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify mismatch between path and internal YAML fields raises ScheduleValidationError."""
        root = tmp_path / "schedules"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
enabled: true
teaching_start_date: "2026-08-01"
teaching_end_date: "2026-12-15"
meeting_rules:
  - weekday: "monday"
""",
            encoding="utf-8",
        )

        repo = ScheduleRepository(root)
        with pytest.raises(ScheduleValidationError, match="mismatched identifiers"):
            repo.get("2026-2", "NEURO")

    def test_io_error_raises_schedule_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify OSError raises ScheduleError."""
        root = tmp_path / "schedules"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("dummy", encoding="utf-8")

        def mock_read_text(*_args: object, **_kwargs: object) -> str:
            raise OSError("Disk read failure")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        repo = ScheduleRepository(root)
        with pytest.raises(ScheduleError, match="Failed to read schedule file"):
            repo.get("2026-2", "NEURO")

    def test_root_dir_property(self, tmp_path: Path) -> None:
        """Verify root_dir returns configured path."""
        repo = ScheduleRepository(tmp_path)
        assert repo.root_dir == tmp_path
