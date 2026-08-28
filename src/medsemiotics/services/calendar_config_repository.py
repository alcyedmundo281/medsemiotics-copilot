"""Repository for loading course calendar configurations from YAML files."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.calendar import CourseCalendarConfig
from medsemiotics.domain.exceptions import (
    CalendarConfigError,
    CalendarConfigNotFoundError,
    CalendarConfigValidationError,
)


class CalendarConfigRepository:
    """Read-only repository for course calendar configurations stored on disk."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize repository with root directory containing calendar configuration folders."""
        self._root_dir = root_dir

    @property
    def root_dir(self) -> Path:
        """Get the root directory of the repository."""
        return self._root_dir

    def _file_path_for(self, semester_id: str, course_code: str) -> tuple[Path, str, str]:
        """Compute expected file path and return normalized identifiers."""
        try:
            norm_sem = validate_and_normalize_semester_id(semester_id)
            norm_course = validate_and_normalize_course_code(course_code)
        except ValueError as err:
            raise CalendarConfigValidationError(str(err)) from err

        return self._root_dir / norm_sem / f"{norm_course}.yaml", norm_sem, norm_course

    def get(self, semester_id: str, course_code: str) -> CourseCalendarConfig:
        """Load and validate a CourseCalendarConfig by semester_id and course_code.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.

        Returns:
            Validated CourseCalendarConfig instance.

        Raises:
            CalendarConfigNotFoundError: If the calendar config file does not exist.
            CalendarConfigValidationError: If the YAML is malformed or fails schema validation.
            CalendarConfigError: For general I/O failures.
        """
        path, norm_sem, norm_course = self._file_path_for(semester_id, course_code)

        if not path.is_file():
            msg = (
                f"Calendar configuration not found for course '{norm_course}' "
                f"in semester '{norm_sem}': {path}"
            )
            raise CalendarConfigNotFoundError(msg)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as err:
            msg = f"Failed to read calendar config file at {path}: {err}"
            raise CalendarConfigError(msg) from err

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as err:
            msg = f"Malformed YAML in calendar config file at {path}: {err}"
            raise CalendarConfigValidationError(msg) from err

        if not isinstance(data, dict):
            msg = (
                f"Invalid calendar config structure at {path}: "
                f"Expected YAML mapping at root, got {type(data).__name__}."
            )
            raise CalendarConfigValidationError(msg)

        try:
            config = CourseCalendarConfig.model_validate(data)
        except ValidationError as err:
            msg = f"Validation failed for calendar config at {path}:\n{err}"
            raise CalendarConfigValidationError(msg) from err

        if config.semester_id != norm_sem or config.course_code != norm_course:
            msg = (
                f"Calendar config at {path} contains mismatched identifiers: "
                f"expected ({norm_sem}, {norm_course}), "
                f"got ({config.semester_id}, {config.course_code})."
            )
            raise CalendarConfigValidationError(msg)

        return config
