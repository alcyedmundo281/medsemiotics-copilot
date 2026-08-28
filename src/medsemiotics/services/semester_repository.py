"""Filesystem-based repository for retrieving semester configurations."""

from pathlib import Path

from medsemiotics.domain.academic import SEMESTER_ID_PATTERN, SemesterConfig
from medsemiotics.domain.exceptions import (
    SemesterConfigNotFoundError,
    SemesterConfigValidationError,
)
from medsemiotics.services.semester_config import load_semester_config


class SemesterRepository:
    """Repository providing read-only access to semester configurations stored on disk."""

    def __init__(self, semesters_dir: Path) -> None:
        """Initialize repository with path to directory containing semester YAML files."""
        self._semesters_dir = semesters_dir

    @property
    def semesters_dir(self) -> Path:
        """Get the base directory for semester configuration files."""
        return self._semesters_dir

    def _file_path_for(self, semester_id: str) -> Path:
        """Compute the expected YAML file path for a semester identifier."""
        cleaned_id = semester_id.strip()
        if not SEMESTER_ID_PATTERN.match(cleaned_id):
            msg = (
                f"Invalid semester ID format '{semester_id}'. "
                "Must match format YYYY-1 or YYYY-2."
            )
            raise SemesterConfigValidationError(msg)
        return self._semesters_dir / f"{cleaned_id}.yaml"

    def get(self, semester_id: str) -> SemesterConfig:
        """Retrieve and validate a semester configuration by ID.

        Args:
            semester_id: Semester identifier, e.g. '2026-2'.

        Returns:
            Validated SemesterConfig instance.

        Raises:
            SemesterConfigNotFoundError: If the semester configuration file does not exist.
            SemesterConfigValidationError: If the semester configuration is malformed or invalid.
        """
        path = self._file_path_for(semester_id)
        if not path.is_file():
            msg = f"Semester '{semester_id}' not found in {self._semesters_dir}"
            raise SemesterConfigNotFoundError(msg)
        config = load_semester_config(path)
        if config.semester_id != semester_id.strip():
            msg = (
                f"File '{path.name}' contains mismatched semester_id "
                f"'{config.semester_id}', expected '{semester_id}'."
            )
            raise SemesterConfigValidationError(msg)
        return config

    def exists(self, semester_id: str) -> bool:
        """Check if a semester configuration file exists for the given ID.

        Args:
            semester_id: Semester identifier, e.g. '2026-2'.

        Returns:
            True if the file exists on disk, False otherwise.
        """
        try:
            path = self._file_path_for(semester_id)
            return path.is_file()
        except SemesterConfigValidationError:
            return False

    def list_semesters(self) -> list[str]:
        """List all available semester identifiers in deterministic sorted order.

        Excludes any non-semester YAML files (such as current_semester.yaml).

        Returns:
            Sorted list of semester_id strings.
        """
        if not self._semesters_dir.is_dir():
            return []

        semester_ids: list[str] = []
        for file in self._semesters_dir.glob("*.yaml"):
            # Exclude current_semester.yaml and any file not matching YYYY-1 or YYYY-2 naming
            stem = file.stem
            if stem == "current_semester":
                continue
            if SEMESTER_ID_PATTERN.match(stem):
                semester_ids.append(stem)

        semester_ids.sort()
        return semester_ids
