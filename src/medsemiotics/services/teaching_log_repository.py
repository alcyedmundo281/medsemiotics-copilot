"""Repository for retrieving teaching session logs from disk."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.exceptions import (
    TeachingLogError,
    TeachingLogNotFoundError,
    TeachingLogValidationError,
)
from medsemiotics.domain.teaching_log import TeachingSession


class TeachingLogRepository:
    """Read-only repository for teaching session logs stored as YAML on disk."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize repository with root directory containing teaching log folders."""
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
            raise TeachingLogValidationError(str(err)) from err

        return self._root_dir / norm_sem / f"{norm_course}.yaml", norm_sem, norm_course

    def get_sessions(self, semester_id: str, course_code: str) -> list[TeachingSession]:
        """Load and validate teaching sessions for a given course and semester.

        Args:
            semester_id: Target semester, e.g. '2026-2'.
            course_code: Target course code, e.g. 'NEURO'.

        Returns:
            List of validated TeachingSession instances. If sessions is empty in YAML, returns [].

        Raises:
            TeachingLogNotFoundError: If the teaching log file does not exist.
            TeachingLogValidationError: If the YAML is malformed or sessions fail validation.
            TeachingLogError: For general I/O or decoding failures.
        """
        path, norm_sem, norm_course = self._file_path_for(semester_id, course_code)

        if not path.is_file():
            msg = (
                f"Teaching log file not found for course '{norm_course}' "
                f"in semester '{norm_sem}': {path}"
            )
            raise TeachingLogNotFoundError(msg)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as err:
            msg = f"Failed to read teaching log file at {path}: {err}"
            raise TeachingLogError(msg) from err

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as err:
            msg = f"Malformed YAML in teaching log file at {path}: {err}"
            raise TeachingLogValidationError(msg) from err

        if not isinstance(data, dict):
            msg = (
                f"Invalid teaching log file structure at {path}: "
                f"Expected YAML mapping at root, got {type(data).__name__}."
            )
            raise TeachingLogValidationError(msg)

        # Optional top-level metadata validation if present
        if "semester_id" in data:
            try:
                top_sem = validate_and_normalize_semester_id(data["semester_id"])
                if top_sem != norm_sem:
                    msg = (
                        f"Teaching log at {path} contains mismatched semester_id: "
                        f"expected '{norm_sem}', got '{top_sem}'."
                    )
                    raise TeachingLogValidationError(msg)
            except ValueError as err:
                raise TeachingLogValidationError(str(err)) from err

        if "course_code" in data:
            try:
                top_course = validate_and_normalize_course_code(data["course_code"])
                if top_course != norm_course:
                    msg = (
                        f"Teaching log at {path} contains mismatched course_code: "
                        f"expected '{norm_course}', got '{top_course}'."
                    )
                    raise TeachingLogValidationError(msg)
            except ValueError as err:
                raise TeachingLogValidationError(str(err)) from err

        raw_sessions = data.get("sessions", [])
        if not isinstance(raw_sessions, list):
            msg = (
                f"Invalid 'sessions' entry in teaching log at {path}: "
                f"Expected list, got {type(raw_sessions).__name__}."
            )
            raise TeachingLogValidationError(msg)

        validated_sessions: list[TeachingSession] = []
        for index, item in enumerate(raw_sessions):
            if not isinstance(item, dict):
                msg = (
                    f"Invalid session entry at index {index} in {path}: "
                    f"Expected mapping, got {type(item).__name__}."
                )
                raise TeachingLogValidationError(msg)
            try:
                session = TeachingSession.model_validate(item)
            except ValidationError as err:
                msg = f"Validation failed for teaching session at index {index} in {path}:\n{err}"
                raise TeachingLogValidationError(msg) from err

            if session.semester_id != norm_sem or session.course_code != norm_course:
                msg = (
                    f"Session '{session.session_id}' in {path} has mismatched identifiers: "
                    f"expected ({norm_sem}, {norm_course}), "
                    f"got ({session.semester_id}, {session.course_code})."
                )
                raise TeachingLogValidationError(msg)

            validated_sessions.append(session)

        return validated_sessions
