"""Unit tests for SemesterRepository."""

from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    SemesterConfigNotFoundError,
    SemesterConfigValidationError,
)
from medsemiotics.services.semester_repository import SemesterRepository


class TestSemesterRepository:
    """Test suite for SemesterRepository filesystem operations."""

    @pytest.fixture
    def setup_semesters_dir(self, tmp_path: Path) -> Path:
        """Create a fixture directory with mock semester files and pointer."""
        semesters_dir = tmp_path / "semesters"
        semesters_dir.mkdir()

        # Valid semesters
        (semesters_dir / "2026-1.yaml").write_text(
            """
semester_id: "2026-1"
display_name: "2026-1"
active: false
courses:
  - code: "NEURO"
    name: "Neurología"
""",
            encoding="utf-8",
        )
        (semesters_dir / "2026-2.yaml").write_text(
            """
semester_id: "2026-2"
display_name: "2026-2"
active: true
courses:
  - code: "NEURO"
    name: "Neurología"
  - code: "GASTRO"
    name: "Gastroenterología"
""",
            encoding="utf-8",
        )
        (semesters_dir / "2027-1.yaml").write_text(
            """
semester_id: "2027-1"
display_name: "2027-1"
active: false
courses:
  - code: "GASTRO"
    name: "Gastroenterología"
""",
            encoding="utf-8",
        )

        # current_semester.yaml pointer in same or parent directory
        (semesters_dir / "current_semester.yaml").write_text(
            'semester_id: "2026-2"\n',
            encoding="utf-8",
        )

        # Unrelated non-semester file
        (semesters_dir / "notes.txt").write_text("Instructor notes", encoding="utf-8")

        return semesters_dir

    def test_get_existing_semester(self, setup_semesters_dir: Path) -> None:
        """Verify retrieving an existing semester returns valid config."""
        repo = SemesterRepository(setup_semesters_dir)
        config = repo.get("2026-2")

        assert config.semester_id == "2026-2"
        assert config.active is True
        assert len(config.courses) == 2

    def test_get_missing_semester_raises_not_found(self, setup_semesters_dir: Path) -> None:
        """Verify requesting a non-existent semester raises SemesterConfigNotFoundError."""
        repo = SemesterRepository(setup_semesters_dir)
        with pytest.raises(SemesterConfigNotFoundError, match="not found"):
            repo.get("2025-1")

    def test_get_invalid_semester_id_format_raises_validation_error(
        self, setup_semesters_dir: Path
    ) -> None:
        """Verify invalid semester ID format raises SemesterConfigValidationError."""
        repo = SemesterRepository(setup_semesters_dir)
        with pytest.raises(SemesterConfigValidationError, match="Invalid semester ID"):
            repo.get("invalid-format")

    def test_exists_true_and_false(self, setup_semesters_dir: Path) -> None:
        """Verify exists returns True for present semesters and False otherwise."""
        repo = SemesterRepository(setup_semesters_dir)
        assert repo.exists("2026-1") is True
        assert repo.exists("2026-2") is True
        assert repo.exists("2025-1") is False
        assert repo.exists("non-existent") is False

    def test_list_semesters_deterministic_and_filtered(self, setup_semesters_dir: Path) -> None:
        """Verify list_semesters returns sorted semester IDs and excludes pointers/other files."""
        repo = SemesterRepository(setup_semesters_dir)
        semesters = repo.list_semesters()

        assert semesters == ["2026-1", "2026-2", "2027-1"]
        assert "current_semester" not in semesters

    def test_list_semesters_empty_directory(self, tmp_path: Path) -> None:
        """Verify list_semesters handles empty or non-existent directories gracefully."""
        empty_dir = tmp_path / "empty_semesters"
        empty_dir.mkdir()
        repo = SemesterRepository(empty_dir)
        assert repo.list_semesters() == []

    def test_list_semesters_non_existent_directory(self, tmp_path: Path) -> None:
        """Verify list_semesters returns empty list if directory does not exist."""
        non_existent_dir = tmp_path / "does_not_exist"
        repo = SemesterRepository(non_existent_dir)
        assert repo.list_semesters() == []

    def test_repository_semesters_dir_property(self, tmp_path: Path) -> None:
        """Verify semesters_dir property returns the configured path."""
        repo = SemesterRepository(tmp_path)
        assert repo.semesters_dir == tmp_path

    def test_get_mismatched_file_content_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify error when filename does not match internal semester_id."""
        semesters_dir = tmp_path / "mismatch"
        semesters_dir.mkdir()
        (semesters_dir / "2026-1.yaml").write_text(
            """
semester_id: "2026-2"
display_name: "2026-2"
active: true
courses:
  - code: "NEURO"
    name: "Neurología"
""",
            encoding="utf-8",
        )
        repo = SemesterRepository(semesters_dir)
        with pytest.raises(SemesterConfigValidationError, match="mismatched semester_id"):
            repo.get("2026-1")
