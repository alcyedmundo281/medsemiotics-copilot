"""Tests for Teaching Coach request, guide, and result contracts."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from medsemiotics.domain.teaching_coach import (
    TeachingCoachDraftRequest,
    TeachingTopicGuide,
)


def make_guide(**updates: object) -> TeachingTopicGuide:
    """Build a valid curated topic guide."""
    values: dict[str, object] = {
        "topic_id": "coordination-cerebellum",
        "topic_title": "Coordinación y cerebelo",
        "learning_objectives": ["Distinguir ataxia cerebelosa de ataxia sensitiva."],
        "critical_points": ["Demostrar marcha, base de sustentación y prueba de Romberg."],
    }
    values.update(updates)
    return TeachingTopicGuide(**values)  # type: ignore[arg-type]


def make_request(**updates: object) -> TeachingCoachDraftRequest:
    """Build a valid timezone-aware draft request."""
    tz = ZoneInfo("America/Guayaquil")
    values: dict[str, object] = {
        "semester_id": "2026-2",
        "course_code": "NEURO",
        "class_date": date(2026, 9, 1),
        "time_min": datetime(2026, 9, 1, 0, 0, tzinfo=tz),
        "time_max": datetime(2026, 9, 2, 0, 0, tzinfo=tz),
        "guide": make_guide(),
        "requested_by": "course-director",
    }
    values.update(updates)
    return TeachingCoachDraftRequest(**values)  # type: ignore[arg-type]


class TestTeachingTopicGuide:
    """Validate faculty-curated source requirements."""

    def test_guide_normalizes_identifier_and_text(self) -> None:
        guide = make_guide(
            topic_id=" Coordination-Cerebellum ",
            topic_title="  Coordinación y cerebelo  ",
        )
        assert guide.topic_id == "coordination-cerebellum"
        assert guide.topic_title == "Coordinación y cerebelo"

    @pytest.mark.parametrize("field_name", ["learning_objectives", "critical_points"])
    def test_required_guide_lists_cannot_be_empty(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="must contain at least one item"):
            make_guide(**{field_name: []})

    def test_duplicate_statements_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="contains duplicate"):
            make_guide(critical_points=["Punto clave", "Punto clave"])

    def test_optional_lists_default_to_empty(self) -> None:
        guide = make_guide()
        assert guide.teaching_questions == []
        assert guide.common_pitfalls == []
        assert guide.material_notes == []

    def test_invalid_supporting_url_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="valid http or https URL"):
            make_guide(powersemiotics_url="not-a-url")


class TestTeachingCoachDraftRequest:
    """Validate explicit scope, requester, and time boundaries."""

    def test_request_normalizes_academic_scope(self) -> None:
        request = make_request(semester_id=" 2026-2 ", course_code=" neuro ")
        assert request.semester_id == "2026-2"
        assert request.course_code == "NEURO"

    def test_naive_time_window_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="time_min must be timezone-aware"):
            make_request(time_min=datetime(2026, 9, 1, 0, 0))

    def test_reversed_time_window_is_rejected(self) -> None:
        tz = ZoneInfo("America/Guayaquil")
        with pytest.raises(ValidationError, match="time_min must be strictly before"):
            make_request(
                time_min=datetime(2026, 9, 2, 0, 0, tzinfo=tz),
                time_max=datetime(2026, 9, 1, 0, 0, tzinfo=tz),
            )

    def test_blank_requester_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requested_by must not be empty"):
            make_request(requested_by="   ")

    def test_class_date_outside_evaluation_window_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="class_date must fall within"):
            make_request(class_date=date(2026, 9, 3))
