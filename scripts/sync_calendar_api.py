#!/usr/bin/env python3
"""Preview the Calendar events an official syllabus implies.

This is a dry run: it contacts no Google API and creates no event. It prints the week, date,
and title of every class so the instructor can compare them against the live calendar.
"""

import sys
from pathlib import Path


def sync_syllabus_to_calendar(yaml_path: str) -> None:
    """List every class of one official syllabus without contacting any calendar."""
    import yaml

    syllabus = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))

    course_name = syllabus["course_info"]["name"]
    calendar_id = syllabus["course_info"]["calendar_id"]
    location = syllabus["course_info"]["location"]
    topics = syllabus["schedule_18_weeks"]

    print("=" * 70)
    print(f"[+] Vista previa de {course_name} (no se contacta ninguna API)...")
    print(f"[*] Calendario ID: {calendar_id}")
    print(f"[*] Ubicacion    : {location}")
    print("=" * 70)

    for item in topics:
        week = item["week"]
        date_str = item["date"]
        title = item["title"]
        status = item["status"]

        print(f"  [Semana {week:02d} - {date_str}] {title} ({status.upper()}) -> {location}")

    print("=" * 70)
    print(f"[OK] {len(topics)} clases listadas para {course_name}. No se creó ningún evento.")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sync_syllabus_to_calendar(sys.argv[1])
    else:
        sync_syllabus_to_calendar("config/syllabi/2026-2/silabo_neurologia_v2.yaml")
        sync_syllabus_to_calendar("config/syllabi/2026-2/silabo_gastroenterologia_v2.yaml")
