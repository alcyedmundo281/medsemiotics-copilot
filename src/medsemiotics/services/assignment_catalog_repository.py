"""Read-only repository for faculty-reviewed assignment and rubric catalogs."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.assignment_catalog import (
    AssignmentRubric,
    AssignmentTemplate,
    CourseAssignmentCatalog,
)
from medsemiotics.domain.exceptions import (
    AssignmentCatalogDisabledError,
    AssignmentCatalogError,
    AssignmentCatalogNotFoundError,
    AssignmentCatalogValidationError,
)


class AssignmentCatalogRepository:
    """Load validated public catalogs without performing external actions."""

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def _file_path_for(self, semester_id: str, course_code: str) -> tuple[Path, str, str]:
        try:
            normalized_semester = validate_and_normalize_semester_id(semester_id)
            normalized_course = validate_and_normalize_course_code(course_code)
        except ValueError as err:
            raise AssignmentCatalogValidationError(str(err)) from err
        path = self._root_dir / normalized_semester / f"{normalized_course}.yaml"
        return path, normalized_semester, normalized_course

    def get_catalog(self, semester_id: str, course_code: str) -> CourseAssignmentCatalog:
        path, normalized_semester, normalized_course = self._file_path_for(
            semester_id,
            course_code,
        )
        if not path.is_file():
            msg = (
                f"Assignment catalog not found for {normalized_course} "
                f"({normalized_semester}): {path}"
            )
            raise AssignmentCatalogNotFoundError(msg)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as err:
            msg = f"Failed to read assignment catalog at {path}: {err}"
            raise AssignmentCatalogError(msg) from err

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as err:
            msg = f"Malformed YAML in assignment catalog at {path}: {err}"
            raise AssignmentCatalogValidationError(msg) from err
        if not isinstance(data, dict):
            msg = (
                f"Invalid assignment catalog structure at {path}: expected YAML mapping, "
                f"got {type(data).__name__}."
            )
            raise AssignmentCatalogValidationError(msg)

        try:
            catalog = CourseAssignmentCatalog.model_validate(data)
        except ValidationError as err:
            msg = f"Validation failed for assignment catalog at {path}:\n{err}"
            raise AssignmentCatalogValidationError(msg) from err

        if catalog.semester_id != normalized_semester or catalog.course_code != normalized_course:
            msg = (
                f"Assignment catalog at {path} contains mismatched identifiers: expected "
                f"({normalized_semester}, {normalized_course}), got "
                f"({catalog.semester_id}, {catalog.course_code})."
            )
            raise AssignmentCatalogValidationError(msg)
        return catalog

    def get_assignment(
        self,
        semester_id: str,
        course_code: str,
        assignment_id: str,
    ) -> AssignmentTemplate:
        catalog = self._enabled_catalog(semester_id, course_code)
        try:
            assignment = catalog.find_assignment(assignment_id)
        except ValueError as err:
            raise AssignmentCatalogValidationError(str(err)) from err
        if assignment is None:
            msg = (
                f"Assignment '{assignment_id}' not found in {catalog.course_code} "
                f"({catalog.semester_id})."
            )
            raise AssignmentCatalogNotFoundError(msg)
        return assignment

    def get_rubric(
        self,
        semester_id: str,
        course_code: str,
        rubric_id: str,
    ) -> AssignmentRubric:
        catalog = self._enabled_catalog(semester_id, course_code)
        try:
            rubric = catalog.find_rubric(rubric_id)
        except ValueError as err:
            raise AssignmentCatalogValidationError(str(err)) from err
        if rubric is None:
            msg = (
                f"Rubric '{rubric_id}' not found in {catalog.course_code} ({catalog.semester_id})."
            )
            raise AssignmentCatalogNotFoundError(msg)
        return rubric

    def _enabled_catalog(self, semester_id: str, course_code: str) -> CourseAssignmentCatalog:
        catalog = self.get_catalog(semester_id, course_code)
        if not catalog.enabled:
            msg = (
                f"Assignment catalog is disabled for {catalog.course_code} ({catalog.semester_id})."
            )
            raise AssignmentCatalogDisabledError(msg)
        return catalog
