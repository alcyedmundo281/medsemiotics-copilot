#!/usr/bin/env python3
"""Generate one iCalendar file per official syllabus, with a real event for every week.

Every timestamp is emitted in UTC. A local time carried as ``DTSTART;TZID=America/Guayaquil``
is only valid when the file also defines that zone in a ``VTIMEZONE`` block, and Google
Calendar imports such a file unreliably. Ecuador observes no daylight saving, so converting
the class hour to UTC once is exact.
"""

from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

COURSE_TIMEZONE = ZoneInfo("America/Guayaquil")
CLASS_START_LOCAL = time(16, 0)
CLASS_DURATION = timedelta(minutes=90)


def generate_ics(yaml_file: str, output_ics: str) -> None:
    """Write one iCalendar file from an official syllabus."""
    data = yaml.safe_load(Path(yaml_file).read_text(encoding="utf-8"))

    course_name = data["course_info"]["name"]
    location = data["course_info"]["location"]
    web_hub = data["course_info"].get("web_hub", "https://powersemiotics.com")
    topics = data["schedule_18_weeks"]

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PowerSemiotics//MedSemiotics Teaching Copilot//ES",
        f"X-WR-CALNAME:{course_name}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for item in topics:
        week = item["week"]
        date_str = item["date"]  # YYYY-MM-DD
        title = item["title"]
        module_url = item.get("web_module", web_hub)

        local_start = datetime.combine(
            datetime.strptime(date_str, "%Y-%m-%d").date(),
            CLASS_START_LOCAL,
            tzinfo=COURSE_TIMEZONE,
        )
        dt_start = local_start.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        dt_end = (local_start + CLASS_DURATION).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        code = data["course_info"]["code"]
        uid = (
            f"medsemiotics-2026-2-{code}-w{week:02d}-{date_str.replace('-', '')}@powersemiotics.com"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{dt_start}",
                f"DTEND:{dt_end}",
                f"SUMMARY:Sem {week:02d} - {title}",
                (
                    f"DESCRIPTION:Clase de {course_name}\\n\\nTema: {title}\\n\\n"
                    f"Modulo Web Interactivo: {module_url}\\n\\nUbicacion: {location}"
                ),
                f"LOCATION:{location}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")

    Path(output_ics).write_text("\r\n".join(lines), encoding="utf-8")
    print(
        f"[OK] Calendario generado en UTC: {output_ics} "
        f"({len(topics)} clases con su tema especifico)"
    )


if __name__ == "__main__":
    generate_ics(
        "config/syllabi/2026-2/silabo_neurologia_v2.yaml", "docs/neurologia_semestre_2026_2.ics"
    )
    generate_ics(
        "config/syllabi/2026-2/silabo_gastroenterologia_v2.yaml",
        "docs/gastroenterologia_semestre_2026_2.ics",
    )
