"""Unit tests for CalendarConfigRepository."""

from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    CalendarConfigError,
    CalendarConfigNotFoundError,
    CalendarConfigValidationError,
)
from medsemiotics.services.calendar_config_repository import (
    CalendarConfigRepository,
)


class TestCalendarConfigRepository:
    """Test suite for CalendarConfigRepository filesystem operations."""

    @pytest.fixture
    def setup_calendar_dir(self, tmp_path: Path) -> Path:
        """Create mock calendar configuration directory."""
        root = tmp_path / "calendar"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)

        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
enabled: false
calendar_id: null
aliases:
  - "Neurología"
  - "Neurologia"
  - "NEURO"
""",
            encoding="utf-8",
        )
        return root

    def test_valid_get(self, setup_calendar_dir: Path) -> None:
        """Verify loading an existing valid calendar config."""
        repo = CalendarConfigRepository(setup_calendar_dir)
        config = repo.get("2026-2", "NEURO")

        assert config.semester_id == "2026-2"
        assert config.course_code == "NEURO"
        assert config.enabled is False
        assert config.calendar_id is None
        assert len(config.aliases) == 3

    def test_missing_file_raises_not_found(self, setup_calendar_dir: Path) -> None:
        """Verify missing config file raises CalendarConfigNotFoundError."""
        repo = CalendarConfigRepository(setup_calendar_dir)
        with pytest.raises(CalendarConfigNotFoundError, match="Calendar configuration not found"):
            repo.get("2026-2", "GASTRO")

    def test_invalid_parameters_raise_validation_error(self, setup_calendar_dir: Path) -> None:
        """Verify invalid semester or course format raises CalendarConfigValidationError."""
        repo = CalendarConfigRepository(setup_calendar_dir)
        with pytest.raises(CalendarConfigValidationError):
            repo.get("invalid_sem", "NEURO")

    def test_malformed_yaml_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify malformed YAML raises CalendarConfigValidationError."""
        root = tmp_path / "calendar"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("semester_id: [unclosed", encoding="utf-8")

        repo = CalendarConfigRepository(root)
        with pytest.raises(CalendarConfigValidationError, match="Malformed YAML"):
            repo.get("2026-2", "NEURO")

    def test_non_dict_root_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify non-mapping root raises CalendarConfigValidationError."""
        root = tmp_path / "calendar"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("- item1\n- item2\n", encoding="utf-8")

        repo = CalendarConfigRepository(root)
        with pytest.raises(CalendarConfigValidationError, match="Expected YAML mapping"):
            repo.get("2026-2", "NEURO")

    def test_mismatched_internal_identifiers_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify mismatch in internal YAML fields raises CalendarConfigValidationError."""
        root = tmp_path / "calendar"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
enabled: false
calendar_id: null
aliases:
  - "GASTRO"
""",
            encoding="utf-8",
        )

        repo = CalendarConfigRepository(root)
        with pytest.raises(CalendarConfigValidationError, match="mismatched identifiers"):
            repo.get("2026-2", "NEURO")

    def test_io_error_raises_calendar_config_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify OSError raises CalendarConfigError."""
        root = tmp_path / "calendar"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("dummy", encoding="utf-8")

        def mock_read_text(*_args: object, **_kwargs: object) -> str:
            raise OSError("Disk failure")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        repo = CalendarConfigRepository(root)
        with pytest.raises(CalendarConfigError, match="Failed to read calendar config file"):
            repo.get("2026-2", "NEURO")

    def test_root_dir_property(self, tmp_path: Path) -> None:
        """Verify root_dir returns configured path."""
        repo = CalendarConfigRepository(tmp_path)
        assert repo.root_dir == tmp_path
