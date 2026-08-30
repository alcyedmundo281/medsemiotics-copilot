"""Repository tests for public assignment/rubric YAML catalogs."""

from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    AssignmentCatalogDisabledError,
    AssignmentCatalogError,
    AssignmentCatalogNotFoundError,
    AssignmentCatalogValidationError,
)
from medsemiotics.services.assignment_catalog_repository import AssignmentCatalogRepository

VALID_CATALOG = """
semester_id: "2026-2"
course_code: "NEURO"
enabled: true
rubrics:
  - rubric_id: "neuro-rubric"
    title: "Neurology rubric"
    levels:
      - level_id: "complete"
        label: "Complete"
        description: "Complete response."
      - level_id: "developing"
        label: "Developing"
        description: "Needs revision."
    criteria:
      - criterion_id: "reasoning"
        title: "Reasoning"
        description: "Explains the localization."
        weight_percent: 100
assignments:
  - assignment_id: "cranial-case"
    topic_id: "cranial-nerves"
    title: "Cranial nerve case"
    prompt: "Analyze a synthetic case."
    deliverables:
      - "Finding table."
    rubric_id: "neuro-rubric"
    suggested_due_days: 7
"""


def write_catalog(root: Path, content: str = VALID_CATALOG) -> Path:
    semester_dir = root / "2026-2"
    semester_dir.mkdir(parents=True)
    path = semester_dir / "NEURO.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestAssignmentCatalogRepository:
    def test_loads_catalog_assignment_and_rubric(self, tmp_path: Path) -> None:
        root = tmp_path / "assignments"
        write_catalog(root)
        repository = AssignmentCatalogRepository(root)

        catalog = repository.get_catalog(" 2026-2 ", " neuro ")
        assignment = repository.get_assignment("2026-2", "NEURO", " Cranial-Case ")
        rubric = repository.get_rubric("2026-2", "NEURO", " Neuro-Rubric ")

        assert catalog.enabled is True
        assert assignment.topic_id == "cranial-nerves"
        assert rubric.criteria[0].weight_percent == 100

    def test_disabled_catalog_blocks_content(self, tmp_path: Path) -> None:
        root = tmp_path / "assignments"
        write_catalog(root, VALID_CATALOG.replace("enabled: true", "enabled: false"))
        repository = AssignmentCatalogRepository(root)
        with pytest.raises(AssignmentCatalogDisabledError, match="disabled"):
            repository.get_assignment("2026-2", "NEURO", "cranial-case")

    def test_missing_catalog_is_controlled(self, tmp_path: Path) -> None:
        with pytest.raises(AssignmentCatalogNotFoundError, match="catalog not found"):
            AssignmentCatalogRepository(tmp_path).get_catalog("2026-2", "NEURO")

    @pytest.mark.parametrize("kind", ["assignment", "rubric"])
    def test_missing_content_is_controlled(self, tmp_path: Path, kind: str) -> None:
        root = tmp_path / "assignments"
        write_catalog(root)
        repository = AssignmentCatalogRepository(root)
        method = repository.get_assignment if kind == "assignment" else repository.get_rubric
        with pytest.raises(AssignmentCatalogNotFoundError, match="not found"):
            method("2026-2", "NEURO", "missing")

    def test_invalid_identifier_is_rejected_before_path_access(self, tmp_path: Path) -> None:
        with pytest.raises(AssignmentCatalogValidationError):
            AssignmentCatalogRepository(tmp_path).get_catalog("../../secret", "NEURO")

    def test_malformed_yaml_is_controlled(self, tmp_path: Path) -> None:
        root = tmp_path / "assignments"
        write_catalog(root, "semester_id: [unclosed")
        with pytest.raises(AssignmentCatalogValidationError, match="Malformed YAML"):
            AssignmentCatalogRepository(root).get_catalog("2026-2", "NEURO")

    def test_non_mapping_yaml_is_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "assignments"
        write_catalog(root, "- assignment\n")
        with pytest.raises(AssignmentCatalogValidationError, match="expected YAML mapping"):
            AssignmentCatalogRepository(root).get_catalog("2026-2", "NEURO")

    def test_mismatched_scope_is_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "assignments"
        write_catalog(root, VALID_CATALOG.replace('course_code: "NEURO"', 'course_code: "GASTRO"'))
        with pytest.raises(AssignmentCatalogValidationError, match="mismatched identifiers"):
            AssignmentCatalogRepository(root).get_catalog("2026-2", "NEURO")

    def test_io_error_is_controlled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "assignments"
        write_catalog(root)

        def fail_read(*_args: object, **_kwargs: object) -> str:
            raise OSError("disk failure")

        monkeypatch.setattr(Path, "read_text", fail_read)
        with pytest.raises(AssignmentCatalogError, match="Failed to read"):
            AssignmentCatalogRepository(root).get_catalog("2026-2", "NEURO")

    def test_root_dir_is_exposed(self, tmp_path: Path) -> None:
        assert AssignmentCatalogRepository(tmp_path).root_dir == tmp_path
