"""Unit tests for SyllabusRepository."""

from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    SyllabusError,
    SyllabusNotFoundError,
    SyllabusValidationError,
)
from medsemiotics.services.syllabus_repository import SyllabusRepository


class TestSyllabusRepository:
    """Test suite for SyllabusRepository filesystem operations."""

    @pytest.fixture
    def setup_syllabus_dir(self, tmp_path: Path) -> Path:
        """Create mock syllabus directory structure."""
        root = tmp_path / "syllabi"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)

        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "NEURO"
topics:
  - topic_id: "neuro-intro"
    planned_order: 1
    planned_week: 1
    required: true
  - topic_id: "mental-status"
    planned_order: 2
    planned_week: 2
    required: true
""",
            encoding="utf-8",
        )

        (sem_dir / "GASTRO.yaml").write_text(
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

        return root

    def test_valid_get(self, setup_syllabus_dir: Path) -> None:
        """Verify loading an existing valid syllabus plan."""
        repo = SyllabusRepository(setup_syllabus_dir)
        plan = repo.get("2026-2", "NEURO")

        assert plan.semester_id == "2026-2"
        assert plan.course_code == "NEURO"
        assert len(plan.topics) == 2

    def test_course_code_case_insensitivity_in_request(self, setup_syllabus_dir: Path) -> None:
        """Verify course_code normalization in get method."""
        repo = SyllabusRepository(setup_syllabus_dir)
        plan = repo.get("  2026-2  ", "  neuro  ")

        assert plan.course_code == "NEURO"
        assert plan.semester_id == "2026-2"

    def test_missing_file_raises_not_found(self, setup_syllabus_dir: Path) -> None:
        """Verify requesting missing syllabus raises SyllabusNotFoundError."""
        repo = SyllabusRepository(setup_syllabus_dir)
        with pytest.raises(SyllabusNotFoundError, match="Syllabus file not found"):
            repo.get("2026-2", "CARDIO")

    def test_invalid_parameters_raise_validation_error(self, setup_syllabus_dir: Path) -> None:
        """Verify invalid semester or course format raises SyllabusValidationError."""
        repo = SyllabusRepository(setup_syllabus_dir)
        with pytest.raises(SyllabusValidationError):
            repo.get("invalid_sem", "NEURO")
        with pytest.raises(SyllabusValidationError):
            repo.get("2026-2", "NEURO@1")

    def test_malformed_yaml_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify unparseable YAML raises SyllabusValidationError."""
        root = tmp_path / "syllabi"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("semester_id: [unclosed", encoding="utf-8")

        repo = SyllabusRepository(root)
        with pytest.raises(SyllabusValidationError, match="Malformed YAML"):
            repo.get("2026-2", "NEURO")

    def test_non_dict_root_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify non-mapping root in YAML raises SyllabusValidationError."""
        root = tmp_path / "syllabi"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("- item1\n- item2\n", encoding="utf-8")

        repo = SyllabusRepository(root)
        with pytest.raises(SyllabusValidationError, match="Expected YAML mapping"):
            repo.get("2026-2", "NEURO")

    def test_mismatched_internal_identifiers_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify internal mismatch between filename and content raises validation error."""
        root = tmp_path / "syllabi"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text(
            """
semester_id: "2026-2"
course_code: "GASTRO"
topics:
  - topic_id: "gastro-intro"
    planned_order: 1
""",
            encoding="utf-8",
        )

        repo = SyllabusRepository(root)
        with pytest.raises(SyllabusValidationError, match="mismatched identifiers"):
            repo.get("2026-2", "NEURO")

    def test_io_error_raises_syllabus_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify OSError raises controlled SyllabusError."""
        root = tmp_path / "syllabi"
        sem_dir = root / "2026-2"
        sem_dir.mkdir(parents=True)
        (sem_dir / "NEURO.yaml").write_text("dummy", encoding="utf-8")

        def mock_read_text(*_args: object, **_kwargs: object) -> str:
            raise OSError("Disk failure")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        repo = SyllabusRepository(root)
        with pytest.raises(SyllabusError, match="Failed to read"):
            repo.get("2026-2", "NEURO")

    def test_root_dir_property(self, tmp_path: Path) -> None:
        """Verify root_dir property returns configured path."""
        repo = SyllabusRepository(tmp_path)
        assert repo.root_dir == tmp_path
