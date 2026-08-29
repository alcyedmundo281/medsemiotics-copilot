"""Read-only repository for faculty-curated Teaching Coach guide catalogs."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.exceptions import (
    TeachingGuideDisabledError,
    TeachingGuideError,
    TeachingGuideNotFoundError,
    TeachingGuideValidationError,
)
from medsemiotics.domain.teaching_coach import (
    CourseTeachingGuideCatalog,
    TeachingTopicGuide,
)
from medsemiotics.domain.topics import validate_and_normalize_topic_id


class TeachingGuideRepository:
    """Load validated guide catalogs from config/teaching_guides without mutations."""

    def __init__(self, root_dir: Path) -> None:
        """Initialize with the root containing semester/course YAML catalogs."""
        self._root_dir = root_dir

    @property
    def root_dir(self) -> Path:
        """Return the configured repository root."""
        return self._root_dir

    def _file_path_for(self, semester_id: str, course_code: str) -> tuple[Path, str, str]:
        """Build a safe path from normalized academic identifiers."""
        try:
            normalized_semester = validate_and_normalize_semester_id(semester_id)
            normalized_course = validate_and_normalize_course_code(course_code)
        except ValueError as err:
            raise TeachingGuideValidationError(str(err)) from err
        path = self._root_dir / normalized_semester / f"{normalized_course}.yaml"
        return path, normalized_semester, normalized_course

    def get_catalog(self, semester_id: str, course_code: str) -> CourseTeachingGuideCatalog:
        """Load and validate one course guide catalog."""
        path, normalized_semester, normalized_course = self._file_path_for(semester_id, course_code)
        if not path.is_file():
            msg = (
                f"Teaching guide catalog not found for {normalized_course} "
                f"({normalized_semester}): {path}"
            )
            raise TeachingGuideNotFoundError(msg)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as err:
            msg = f"Failed to read teaching guide catalog at {path}: {err}"
            raise TeachingGuideError(msg) from err

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as err:
            msg = f"Malformed YAML in teaching guide catalog at {path}: {err}"
            raise TeachingGuideValidationError(msg) from err
        if not isinstance(data, dict):
            msg = (
                f"Invalid teaching guide catalog structure at {path}: "
                f"expected YAML mapping, got {type(data).__name__}."
            )
            raise TeachingGuideValidationError(msg)

        try:
            catalog = CourseTeachingGuideCatalog.model_validate(data)
        except ValidationError as err:
            msg = f"Validation failed for teaching guide catalog at {path}:\n{err}"
            raise TeachingGuideValidationError(msg) from err

        if catalog.semester_id != normalized_semester or catalog.course_code != normalized_course:
            msg = (
                f"Teaching guide catalog at {path} contains mismatched identifiers: "
                f"expected ({normalized_semester}, {normalized_course}), got "
                f"({catalog.semester_id}, {catalog.course_code})."
            )
            raise TeachingGuideValidationError(msg)
        return catalog

    def get_guide(
        self,
        semester_id: str,
        course_code: str,
        topic_id: str,
    ) -> TeachingTopicGuide:
        """Return one guide only when its course catalog is explicitly enabled."""
        catalog = self.get_catalog(semester_id, course_code)
        if not catalog.enabled:
            msg = (
                f"Teaching guide catalog is disabled for {catalog.course_code} "
                f"({catalog.semester_id})."
            )
            raise TeachingGuideDisabledError(msg)

        try:
            normalized_topic = validate_and_normalize_topic_id(topic_id)
        except ValueError as err:
            raise TeachingGuideValidationError(str(err)) from err
        guide = catalog.find_guide(normalized_topic)
        if guide is None:
            msg = (
                f"Teaching guide for topic '{normalized_topic}' not found in "
                f"{catalog.course_code} ({catalog.semester_id})."
            )
            raise TeachingGuideNotFoundError(msg)
        return guide
