"""Tests for the read-only YAML Teaching Guide repository."""

from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    TeachingGuideDisabledError,
    TeachingGuideError,
    TeachingGuideNotFoundError,
    TeachingGuideValidationError,
)
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository

VALID_CATALOG = """
semester_id: "2026-2"
course_code: "NEURO"
enabled: true
guides:
  - topic_id: "coordination-cerebellum"
    topic_title: "Coordinación y cerebelo"
    learning_objectives:
      - "Distinguir patrones de ataxia."
    critical_points:
      - "Comparar marcha y prueba de Romberg."
"""


def write_catalog(root: Path, content: str = VALID_CATALOG) -> Path:
    """Create a NEURO guide catalog fixture."""
    semester_dir = root / "2026-2"
    semester_dir.mkdir(parents=True)
    path = semester_dir / "NEURO.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestTeachingGuideRepository:
    """Verify controlled loading and explicit activation behavior."""

    def test_loads_valid_catalog_and_topic(self, tmp_path: Path) -> None:
        root = tmp_path / "teaching_guides"
        write_catalog(root)
        repository = TeachingGuideRepository(root)

        catalog = repository.get_catalog(" 2026-2 ", " neuro ")
        guide = repository.get_guide("2026-2", "NEURO", " Coordination-Cerebellum ")

        assert catalog.enabled is True
        assert guide.topic_title == "Coordinación y cerebelo"

    def test_disabled_catalog_blocks_topic_retrieval(self, tmp_path: Path) -> None:
        root = tmp_path / "teaching_guides"
        write_catalog(
            root,
            'semester_id: "2026-2"\ncourse_code: "NEURO"\nenabled: false\nguides: []\n',
        )
        repository = TeachingGuideRepository(root)

        with pytest.raises(TeachingGuideDisabledError, match="catalog is disabled"):
            repository.get_guide("2026-2", "NEURO", "neuro-intro")

    def test_missing_catalog_is_controlled(self, tmp_path: Path) -> None:
        repository = TeachingGuideRepository(tmp_path)
        with pytest.raises(TeachingGuideNotFoundError, match="catalog not found"):
            repository.get_catalog("2026-2", "NEURO")

    def test_missing_topic_is_controlled(self, tmp_path: Path) -> None:
        root = tmp_path / "teaching_guides"
        write_catalog(root)
        repository = TeachingGuideRepository(root)
        with pytest.raises(TeachingGuideNotFoundError, match="topic 'cranial-nerves'"):
            repository.get_guide("2026-2", "NEURO", "cranial-nerves")

    def test_invalid_identifiers_are_rejected_before_path_access(self, tmp_path: Path) -> None:
        repository = TeachingGuideRepository(tmp_path)
        with pytest.raises(TeachingGuideValidationError):
            repository.get_catalog("../../secrets", "NEURO")
        with pytest.raises(TeachingGuideValidationError):
            repository.get_catalog("2026-2", "NEURO@1")

    def test_malformed_yaml_is_controlled(self, tmp_path: Path) -> None:
        root = tmp_path / "teaching_guides"
        write_catalog(root, "semester_id: [unclosed")
        repository = TeachingGuideRepository(root)
        with pytest.raises(TeachingGuideValidationError, match="Malformed YAML"):
            repository.get_catalog("2026-2", "NEURO")

    def test_non_mapping_yaml_is_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "teaching_guides"
        write_catalog(root, "- guide-one\n- guide-two\n")
        repository = TeachingGuideRepository(root)
        with pytest.raises(TeachingGuideValidationError, match="expected YAML mapping"):
            repository.get_catalog("2026-2", "NEURO")

    def test_mismatched_internal_scope_is_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "teaching_guides"
        write_catalog(root, VALID_CATALOG.replace('course_code: "NEURO"', 'course_code: "GASTRO"'))
        repository = TeachingGuideRepository(root)
        with pytest.raises(TeachingGuideValidationError, match="mismatched identifiers"):
            repository.get_catalog("2026-2", "NEURO")

    def test_io_error_is_controlled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "teaching_guides"
        write_catalog(root)

        def fail_read(*_args: object, **_kwargs: object) -> str:
            raise OSError("disk failure")

        monkeypatch.setattr(Path, "read_text", fail_read)
        repository = TeachingGuideRepository(root)
        with pytest.raises(TeachingGuideError, match="Failed to read"):
            repository.get_catalog("2026-2", "NEURO")

    def test_root_dir_is_exposed(self, tmp_path: Path) -> None:
        repository = TeachingGuideRepository(tmp_path)
        assert repository.root_dir == tmp_path
