"""Repository for retrieving course syllabus plans from disk."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.exceptions import (
    SyllabusError,
    SyllabusNotFoundError,
    SyllabusValidationError,
)
from medsemiotics.domain.syllabus import SyllabusPlan


class SyllabusRepository:
    """Read-only repository for syllabus plans stored as YAML on disk."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize repository with root directory containing syllabus folders."""
        self._root_dir = root_dir

    @property
    def root_dir(self) -> Path:
        """Get the root directory of the repository."""
        return self._root_dir

    def _file_path_for(self, semester_id: str, course_code: str) -> tuple[Path, str, str]:
        """Compute the expected file path and return normalized identifiers."""
        try:
            norm_sem = validate_and_normalize_semester_id(semester_id)
            norm_course = validate_and_normalize_course_code(course_code)
        except ValueError as err:
            raise SyllabusValidationError(str(err)) from err

        return self._root_dir / norm_sem / f"{norm_course}.yaml", norm_sem, norm_course

    def get(self, semester_id: str, course_code: str) -> SyllabusPlan:
        """Load and validate a SyllabusPlan by semester_id and course_code.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.

        Returns:
            Validated SyllabusPlan instance.

        Raises:
            SyllabusNotFoundError: If the syllabus file does not exist.
            SyllabusValidationError: If the syllabus YAML is malformed or invalid.
            SyllabusError: For general I/O or decoding failures.
        """
        path, norm_sem, norm_course = self._file_path_for(semester_id, course_code)

        if not path.is_file():
            msg = (
                f"Syllabus file not found for course '{norm_course}' "
                f"in semester '{norm_sem}': {path}"
            )
            raise SyllabusNotFoundError(msg)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as err:
            msg = f"Failed to read syllabus file at {path}: {err}"
            raise SyllabusError(msg) from err

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as err:
            msg = f"Malformed YAML in syllabus file at {path}: {err}"
            raise SyllabusValidationError(msg) from err

        if not isinstance(data, dict):
            msg = (
                f"Invalid syllabus file structure at {path}: "
                f"Expected YAML mapping at root, got {type(data).__name__}."
            )
            raise SyllabusValidationError(msg)

        try:
            plan = SyllabusPlan.model_validate(data)
        except ValidationError as err:
            msg = f"Validation failed for syllabus plan at {path}:\n{err}"
            raise SyllabusValidationError(msg) from err

        if plan.semester_id != norm_sem or plan.course_code != norm_course:
            msg = (
                f"Syllabus file at {path} contains mismatched identifiers: "
                f"expected ({norm_sem}, {norm_course}), "
                f"got ({plan.semester_id}, {plan.course_code})."
            )
            raise SyllabusValidationError(msg)

        return plan
