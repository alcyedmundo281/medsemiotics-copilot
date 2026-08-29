"""Tests for faculty-curated course teaching guide catalogs."""

import pytest
from pydantic import ValidationError

from medsemiotics.domain.teaching_coach import (
    CourseTeachingGuideCatalog,
    TeachingTopicGuide,
)


def make_guide(topic_id: str = "coordination-cerebellum") -> TeachingTopicGuide:
    return TeachingTopicGuide(
        topic_id=topic_id,
        topic_title="Coordinación y cerebelo",
        learning_objectives=["Distinguir patrones de ataxia."],
        critical_points=["Comparar marcha y prueba de Romberg."],
    )


class TestCourseTeachingGuideCatalog:
    """Verify activation and topic uniqueness invariants."""

    def test_disabled_empty_placeholder_is_valid(self) -> None:
        catalog = CourseTeachingGuideCatalog(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=False,
            guides=[],
        )
        assert catalog.enabled is False
        assert catalog.guides == []

    def test_enabled_catalog_requires_content(self) -> None:
        with pytest.raises(ValidationError, match="must contain at least one guide"):
            CourseTeachingGuideCatalog(
                semester_id="2026-2",
                course_code="NEURO",
                enabled=True,
                guides=[],
            )

    def test_duplicate_topic_guides_are_rejected(self) -> None:
        guide = make_guide()
        with pytest.raises(ValidationError, match="duplicate topic guides"):
            CourseTeachingGuideCatalog(
                semester_id="2026-2",
                course_code="NEURO",
                enabled=True,
                guides=[guide, guide],
            )

    def test_find_guide_normalizes_topic_identifier(self) -> None:
        guide = make_guide()
        catalog = CourseTeachingGuideCatalog(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=True,
            guides=[guide],
        )
        assert catalog.find_guide(" Coordination-Cerebellum ") is guide
        assert catalog.find_guide("cranial-nerves") is None
