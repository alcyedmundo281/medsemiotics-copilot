"""Pure, read-only services for loading and validating semester configuration YAML files."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from medsemiotics.domain.academic import SEMESTER_ID_PATTERN, SemesterConfig
from medsemiotics.domain.exceptions import (
    SemesterConfigError,
    SemesterConfigNotFoundError,
    SemesterConfigValidationError,
)


def load_semester_config(path: Path) -> SemesterConfig:
    """Load and validate a SemesterConfig from a YAML file.

    Args:
        path: Filesystem path to the semester YAML file.

    Returns:
        Validated SemesterConfig instance.

    Raises:
        SemesterConfigNotFoundError: If the file does not exist.
        SemesterConfigValidationError: If YAML syntax is invalid or schema validation fails.
        SemesterConfigError: For general I/O or decoding failures.
    """
    if not path.is_file():
        msg = f"Semester configuration file not found: {path}"
        raise SemesterConfigNotFoundError(msg)

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as err:
        msg = f"Failed to read semester configuration file at {path}: {err}"
        raise SemesterConfigError(msg) from err

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as err:
        msg = f"Malformed YAML in semester configuration at {path}: {err}"
        raise SemesterConfigValidationError(msg) from err

    if not isinstance(data, dict):
        msg = (
            f"Invalid semester configuration at {path}: "
            f"Expected a YAML mapping at root, got {type(data).__name__}."
        )
        raise SemesterConfigValidationError(msg)

    try:
        return SemesterConfig.model_validate(data)
    except ValidationError as err:
        msg = f"Validation failed for semester configuration at {path}:\n{err}"
        raise SemesterConfigValidationError(msg) from err


def load_current_semester_id(path: Path) -> str:
    """Load and validate the current semester ID from a pointer YAML file.

    Args:
        path: Filesystem path to the current_semester.yaml pointer file.

    Returns:
        Validated semester_id string (e.g. '2026-2').

    Raises:
        SemesterConfigNotFoundError: If the pointer file does not exist.
        SemesterConfigValidationError: If YAML is invalid or semester_id format is invalid.
        SemesterConfigError: For general I/O or decoding failures.
    """
    if not path.is_file():
        msg = f"Current semester pointer file not found: {path}"
        raise SemesterConfigNotFoundError(msg)

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as err:
        msg = f"Failed to read current semester pointer at {path}: {err}"
        raise SemesterConfigError(msg) from err

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as err:
        msg = f"Malformed YAML in current semester pointer at {path}: {err}"
        raise SemesterConfigValidationError(msg) from err

    if not isinstance(data, dict):
        msg = (
            f"Invalid current semester pointer at {path}: "
            f"Expected a YAML mapping at root, got {type(data).__name__}."
        )
        raise SemesterConfigValidationError(msg)

    raw_id = data.get("semester_id")
    if not isinstance(raw_id, str):
        msg = (
            f"Missing or invalid 'semester_id' in pointer at {path}. "
            f"Expected string, got {type(raw_id).__name__}."
        )
        raise SemesterConfigValidationError(msg)

    cleaned_id = raw_id.strip()
    if not SEMESTER_ID_PATTERN.match(cleaned_id):
        msg = (
            f"Invalid 'semester_id' value '{cleaned_id}' in pointer at {path}. "
            "Must match format YYYY-1 or YYYY-2."
        )
        raise SemesterConfigValidationError(msg)

    return cleaned_id
