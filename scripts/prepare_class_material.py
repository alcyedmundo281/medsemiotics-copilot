#!/usr/bin/env python3
"""Prepare the teaching document and the Classroom draft for a course's next class.

The topic, its title, its date and its web module come from the official syllabus, and the
teaching content comes from the curated guide catalog, so this works for every week of the
semester rather than for one hardcoded topic.

Nothing is published. The document is written under ``docs/`` and, when a materials directory is
given, copied there for the instructor to review and share.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from medsemiotics.domain.exceptions import TeachingGuideError  # noqa: E402
from medsemiotics.integrations.classroom.browser_publisher import (  # noqa: E402
    ClassroomBrowserPublisher,
)
from medsemiotics.services.teaching_guide_repository import (  # noqa: E402
    TeachingGuideRepository,
)

CONFIG_ROOT = REPO_ROOT / "config"
DOCS_ROOT = REPO_ROOT / "docs"
SEMESTER_ID = "2026-2"

# The instructor's own materials folder is machine-specific and is never tracked here. Pass it
# with --materials-dir, or set MEDSEMIOTICS_MATERIALS_DIR in the environment.
MATERIALS_DIR_ENV_VAR = "MEDSEMIOTICS_MATERIALS_DIR"

COURSES: dict[str, tuple[str, str]] = {
    "NEURO": ("silabo_neurologia_v2.yaml", "Neurología"),
    "GASTRO": ("silabo_gastroenterologia_v2.yaml", "Gastroenterología"),
}


def next_pending_week(course_code: str) -> dict[str, Any]:
    """Return the first week of the official syllabus that is not completed yet."""
    source, _ = COURSES[course_code]
    syllabus = yaml.safe_load(
        (CONFIG_ROOT / "syllabi" / SEMESTER_ID / source).read_text(encoding="utf-8")
    )
    weeks = sorted(syllabus["schedule_18_weeks"], key=lambda week: int(week["week"]))
    pending = [week for week in weeks if week["status"] != "completed"]
    if not pending:
        msg = f"The official {course_code} syllabus reports no pending week."
        raise SystemExit(msg)
    return {"course_info": syllabus["course_info"], **pending[0]}


def render_document(course_code: str, week: dict[str, Any]) -> str:
    """Render the class document from the syllabus week and its curated guide."""
    info = week["course_info"]
    guide = TeachingGuideRepository(CONFIG_ROOT / "teaching_guides").get_guide(
        SEMESTER_ID, course_code, str(week["topic_id"])
    )

    def section(heading: str, items: object) -> list[str]:
        entries = list(items) if isinstance(items, (list, tuple)) else []
        if not entries:
            return []
        return [f"## {heading}", "", *[f"- {entry}" for entry in entries], ""]

    lines = [
        f"# {guide.topic_title}",
        "",
        f"**{info['name']} — semestre {SEMESTER_ID}**",
        "",
        f"Semana {int(week['week']):02d} · {week['date']} · {info['schedule']}",
        "",
        f"{info['hospital_rotation']} · {info['location']}",
        "",
        f"> Tema oficial del sílabo: {week['title']}",
        "",
        "---",
        "",
    ]
    lines += section("Objetivos de aprendizaje", guide.learning_objectives)
    lines += section("Puntos críticos", guide.critical_points)
    lines += section("Preguntas para la clase", guide.teaching_questions)
    lines += section("Errores frecuentes", guide.common_pitfalls)
    lines += section("Material de apoyo", guide.material_notes)

    module_url = str(week.get("web_module", info.get("web_hub", "")))
    if module_url:
        lines += [f"Módulo interactivo: {module_url}", ""]
    lines += [
        "---",
        "",
        "Documento de trabajo docente. Los casos empleados en clase son sintéticos o "
        "desidentificados.",
        "",
    ]
    return "\n".join(lines)


def resolve_materials_dir(argument: str | None) -> Path | None:
    """Resolve the instructor's materials directory from the argument or the environment."""
    raw = argument or os.getenv(MATERIALS_DIR_ENV_VAR) or ""
    return Path(raw) if raw.strip() else None


def main(argv: list[str] | None = None) -> int:
    """Write the class document and print the Classroom draft for a course's next class."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course", default="NEURO", choices=sorted(COURSES))
    parser.add_argument("--section", default="Segundo Hemisemestre", help="Tema en Classroom")
    parser.add_argument(
        "--materials-dir",
        default=None,
        help=f"Carpeta local donde copiar el documento (o {MATERIALS_DIR_ENV_VAR}).",
    )
    args = parser.parse_args(argv)

    course_code = str(args.course)
    week = next_pending_week(course_code)
    _, course_name = COURSES[course_code]

    try:
        document = render_document(course_code, week)
    except TeachingGuideError as error:
        print(f"[!] Sin guía curada para '{week['topic_id']}': {type(error).__name__}")
        print("    Cure la guía en config/teaching_guides antes de preparar la clase.")
        return 1

    print("=" * 75)
    print(f"[+] {week['course_info']['name']}")
    print(f"[*] Semana {int(week['week']):02d} ({week['date']}) — {week['title']}")
    print("=" * 75)

    document_path = DOCS_ROOT / f"guia_clinica_{course_code.lower()}_{week['topic_id']}.md"
    document_path.write_text(document, encoding="utf-8")
    print(f"[OK] Documento de clase escrito en: {document_path.relative_to(REPO_ROOT)}")

    materials_dir = resolve_materials_dir(args.materials_dir)
    if materials_dir is None:
        print(f"[i] Sin carpeta de materiales configurada ({MATERIALS_DIR_ENV_VAR}); no se copió.")
    elif not materials_dir.is_dir():
        print(f"[!] La carpeta de materiales no existe; no se copió: {materials_dir}")
    else:
        copied = materials_dir / document_path.name
        copied.write_text(document, encoding="utf-8")
        print(f"[OK] Copiado a la carpeta de materiales: {copied}")

    module_url = str(week.get("web_module", "") or "")
    plan = ClassroomBrowserPublisher().plan_material(
        course_name=course_name,
        title=f"Guía de clase: {week['title']}",
        description=(
            f"Material complementario de la clase de la semana {int(week['week']):02d} "
            f"({week['date']}): {week['title']}."
            + (f"\n\nMódulo interactivo: {module_url}" if module_url else "")
            + f"\n\nCátedra de {course_name}"
        ),
        topic_name=str(args.section),
        links=[module_url] if module_url else None,
    )
    print()
    print(plan.render())
    print("\nBORRADOR. Nada fue publicado: revise y publique usted en Google Classroom.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
