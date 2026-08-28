"""Unit tests for coaching brief description and title formatting."""

from datetime import date

from medsemiotics.domain.coaching import CoachingBrief
from medsemiotics.services.coaching_formatter import (
    build_teaching_event_title,
    format_coaching_brief,
)


class TestCoachingFormatter:
    """Test suite for format_coaching_brief and build_teaching_event_title."""

    def test_build_teaching_event_title(self) -> None:
        """Verify building clean event title."""
        title = build_teaching_event_title(course_code="NEURO", topic_title="Síndrome cerebeloso")
        assert title == "NEURO — Síndrome cerebeloso"

    def test_format_complete_coaching_brief(self) -> None:
        """Verify formatting a full CoachingBrief produces expected structured sections."""
        brief = CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
            topic_id="t1",
            topic_title="Síndrome cerebeloso",
            learning_objectives=[
                "Reconocer los signos cardinales.",
                "Diferenciar ataxia cerebelosa de sensitiva.",
            ],
            coaching_tips=[
                "Iniciar con examen de marcha.",
                "Hacer énfasis en dismetría.",
            ],
            teaching_questions=[
                "¿Qué es el temblor intencional?",
            ],
            common_pitfalls=[
                "Confundir dismetría con debilidad piramidal.",
            ],
            material_notes=[
                "Martillo de reflejos.",
            ],
            assignment_note="Revisar caso clínico 3 en PowerSemiotics.",
            powersemiotics_url="https://powersemiotics.org/cases/cerebellar-1",
        )

        formatted = format_coaching_brief(brief)

        assert "MEDSEMIOTICS TEACHING COPILOT" in formatted
        assert "Tema:\nSíndrome cerebeloso" in formatted
        assert "Objetivos:\n• Reconocer los signos cardinales.\n• Diferenciar ataxia cerebelosa de sensitiva." in formatted
        assert "Coach para la clase:\n• Iniciar con examen de marcha.\n• Hacer énfasis en dismetría." in formatted
        assert "Preguntas disparadoras:\n• ¿Qué es el temblor intencional?" in formatted
        assert "Errores frecuentes:\n• Confundir dismetría con debilidad piramidal." in formatted
        assert "Material:\n• Martillo de reflejos." in formatted
        assert "Tarea:\nRevisar caso clínico 3 en PowerSemiotics." in formatted
        assert "PowerSemiotics:\nhttps://powersemiotics.org/cases/cerebellar-1" in formatted
        assert "Generated/managed by MedSemiotics Teaching Copilot." in formatted

    def test_format_brief_with_empty_optional_sections(self) -> None:
        """Verify empty optional sections are omitted cleanly."""
        brief = CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
            topic_title="Introducción a la Neurología",
        )

        formatted = format_coaching_brief(brief)

        assert "MEDSEMIOTICS TEACHING COPILOT" in formatted
        assert "Tema:\nIntroducción a la Neurología" in formatted
        assert "Objetivos:" not in formatted
        assert "Coach para la clase:" not in formatted
        assert "Preguntas disparadoras:" not in formatted
        assert "Errores frecuentes:" not in formatted
        assert "Material:" not in formatted
        assert "Tarea:" not in formatted
        assert "PowerSemiotics:" not in formatted
        assert "Generated/managed by MedSemiotics Teaching Copilot." in formatted
