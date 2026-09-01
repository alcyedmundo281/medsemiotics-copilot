#!/usr/bin/env python3
"""Prepare the Classroom material draft for the next class of a course.

The topic, its title, and its web module come from the official syllabus, so the draft always
matches what is actually taught next. Nothing is published: the draft is printed for review.
"""

import argparse
import sys
from pathlib import Path

import yaml

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from medsemiotics.integrations.classroom.browser_publisher import (  # noqa: E402
    ClassroomBrowserPublisher,
)

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
SEMESTER_ID = "2026-2"
OFFICIAL_SYLLABI = {
    "NEURO": ("silabo_neurologia_v2.yaml", "Neurología"),
    "GASTRO": ("silabo_gastroenterologia_v2.yaml", "Gastroenterología"),
}


def next_week(course_code: str) -> dict[str, object]:
    """Return the first week of the official syllabus that is not completed yet."""
    source, _ = OFFICIAL_SYLLABI[course_code]
    path = CONFIG_ROOT / "syllabi" / SEMESTER_ID / source
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    weeks = sorted(data["schedule_18_weeks"], key=lambda week: int(week["week"]))
    pending = [week for week in weeks if week["status"] != "completed"]
    if not pending:
        msg = f"The official {course_code} syllabus reports no pending week."
        raise SystemExit(msg)
    return dict(pending[0])


def main() -> int:
    """Print the reviewable Classroom draft for a course's next class."""
    parser = argparse.ArgumentParser(description="Prepare the next class material draft")
    parser.add_argument("--course", default="NEURO", choices=sorted(OFFICIAL_SYLLABI))
    parser.add_argument("--section", default="Segundo Hemisemestre", help="Classroom topic")
    args = parser.parse_args()

    week = next_week(args.course)
    _, course_name = OFFICIAL_SYLLABI[args.course]
    module_url = str(week.get("web_module", ""))

    description_lines = [
        "Estimados estudiantes:",
        "",
        f"Material complementario de la clase de la semana {int(week['week']):02d} "
        f"({week['date']}): {week['title']}.",
    ]
    if module_url:
        description_lines += ["", f"Módulo web interactivo: {module_url}"]
    description_lines += ["", f"Cátedra de {course_name}"]

    plan = ClassroomBrowserPublisher().plan_material(
        course_name=course_name,
        title=f"Guía de clase: {week['title']}",
        description="\n".join(description_lines),
        topic_name=args.section,
        links=[module_url] if module_url else None,
    )
    print(plan.render())
    print("\nBORRADOR. Nada fue publicado: revise y publique usted en Google Classroom.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
