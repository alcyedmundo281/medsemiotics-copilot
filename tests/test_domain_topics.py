"""Unit tests for Topic domain model."""

import pytest
from pydantic import ValidationError

from medsemiotics.domain.topics import Topic


class TestTopicDomainModel:
    """Test suite for Topic validation, normalization, and immutability."""

    def test_valid_topic(self) -> None:
        """Verify standard topic creation."""
        topic = Topic(
            topic_id="neuro-intro",
            course_code="NEURO",
            title="Introducción a la Semiología Neurológica",
            description="Conceptos iniciales y examen neurológico general.",
            active=True,
        )
        assert topic.topic_id == "neuro-intro"
        assert topic.course_code == "NEURO"
        assert topic.title == "Introducción a la Semiología Neurológica"
        assert topic.description == "Conceptos iniciales y examen neurológico general."
        assert topic.active is True

    def test_topic_id_normalization_lowercase_and_trim(self) -> None:
        """Verify topic_id is trimmed and normalized to lowercase."""
        topic = Topic(
            topic_id="  STROKE_ISCHEMIC-01  ",
            course_code="neuro",
            title="Ictus Isquémico",
        )
        assert topic.topic_id == "stroke_ischemic-01"
        assert topic.course_code == "NEURO"

    @pytest.mark.parametrize(
        "invalid_topic_id",
        [
            "",
            "   ",
            "neuro intro",
            "stroke/ischemic",
            "neuro.intro",
            "topic@1",
            "topic#2",
        ],
    )
    def test_invalid_topic_ids(self, invalid_topic_id: str) -> None:
        """Verify rejection of invalid topic ID formats."""
        with pytest.raises(ValidationError):
            Topic(
                topic_id=invalid_topic_id,
                course_code="NEURO",
                title="Invalid Topic ID Test",
            )

    @pytest.mark.parametrize(
        ("raw_desc", "expected"),
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("  Detailed notes  ", "Detailed notes"),
        ],
    )
    def test_description_normalization(self, raw_desc: str | None, expected: str | None) -> None:
        """Verify description whitespace trimming and normalization of empty string to None."""
        topic = Topic(
            topic_id="gastro-intro",
            course_code="GASTRO",
            title="Introducción a la Semiología Gastrointestinal",
            description=raw_desc,
        )
        assert topic.description == expected

    @pytest.mark.parametrize("invalid_title", ["", "   "])
    def test_invalid_empty_title(self, invalid_title: str) -> None:
        """Verify empty or whitespace-only title is rejected."""
        with pytest.raises(ValidationError):
            Topic(
                topic_id="valid-id",
                course_code="NEURO",
                title=invalid_title,
            )

    def test_topic_immutability(self) -> None:
        """Verify Topic instance cannot be mutated."""
        topic = Topic(
            topic_id="cranial-nerves",
            course_code="NEURO",
            title="Pares Craneales",
        )
        with pytest.raises(ValidationError):
            topic.title = "New Title"  # type: ignore[misc]

    @pytest.mark.parametrize("invalid_val", [123, ["list"], {"key": "val"}])
    def test_topic_non_string_types(self, invalid_val: object) -> None:
        """Verify passing non-string values raises ValidationError."""
        with pytest.raises(ValidationError):
            Topic(topic_id=invalid_val, course_code="NEURO", title="Title")  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            Topic(topic_id="id", course_code="NEURO", title=invalid_val)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            Topic(topic_id="id", course_code="NEURO", title="Title", description=invalid_val)  # type: ignore[arg-type]
