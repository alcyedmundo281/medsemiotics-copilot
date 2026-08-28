"""Deterministic plain-text formatter for coaching briefings and calendar event titles."""

from medsemiotics.domain.coaching import CoachingBrief


def build_teaching_event_title(*, course_code: str, topic_title: str) -> str:
    """Build a deterministic calendar event title for a teaching session."""
    clean_code = course_code.strip()
    clean_title = topic_title.strip()
    return f"{clean_code} — {clean_title}"


def format_coaching_brief(brief: CoachingBrief) -> str:
    """Format a CoachingBrief into a structured, readable plain-text calendar description."""
    sections: list[str] = ["MEDSEMIOTICS TEACHING COPILOT"]

    # 1. Topic Title
    sections.append(f"Tema:\n{brief.topic_title.strip()}")

    # 2. Learning Objectives
    if brief.learning_objectives:
        bullet_list = "\n".join(f"• {obj}" for obj in brief.learning_objectives)
        sections.append(f"Objetivos:\n{bullet_list}")

    # 3. Coaching Tips
    if brief.coaching_tips:
        bullet_list = "\n".join(f"• {tip}" for tip in brief.coaching_tips)
        sections.append(f"Coach para la clase:\n{bullet_list}")

    # 4. Trigger Questions
    if brief.teaching_questions:
        bullet_list = "\n".join(f"• {q}" for q in brief.teaching_questions)
        sections.append(f"Preguntas disparadoras:\n{bullet_list}")

    # 5. Common Pitfalls
    if brief.common_pitfalls:
        bullet_list = "\n".join(f"• {pf}" for pf in brief.common_pitfalls)
        sections.append(f"Errores frecuentes:\n{bullet_list}")

    # 6. Material Notes
    if brief.material_notes:
        bullet_list = "\n".join(f"• {mat}" for mat in brief.material_notes)
        sections.append(f"Material:\n{bullet_list}")

    # 7. Assignment Note
    if brief.assignment_note:
        sections.append(f"Tarea:\n{brief.assignment_note.strip()}")

    # 8. PowerSemiotics URL
    if brief.powersemiotics_url:
        sections.append(f"PowerSemiotics:\n{brief.powersemiotics_url.strip()}")

    # 9. Footer
    sections.append("Generated/managed by MedSemiotics Teaching Copilot.")

    return "\n\n".join(sections)
