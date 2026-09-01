#!/usr/bin/env python3
"""Generador de archivos iCalendar (.ics) con los 18 temas individuales específicos del Sílabo."""

import yaml
from pathlib import Path
from datetime import datetime

def generate_ics(yaml_file: str, output_ics: str):
    with open(yaml_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    course_name = data['course_info']['name']
    location = data['course_info']['location']
    web_hub = data['course_info'].get('web_hub', 'https://powersemiotics.com')
    topics = data['schedule_18_weeks']

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PowerSemiotics//MedSemiotics Teaching Copilot//ES",
        f"X-WR-CALNAME:{course_name}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]

    for item in topics:
        week = item['week']
        date_str = item['date']  # YYYY-MM-DD
        title = item['title']
        module_url = item.get('web_module', web_hub)

        dt_start = date_str.replace("-", "") + "T160000"
        dt_end = date_str.replace("-", "") + "T173000"
        uid = f"medsemiotics-2026-2-{data['course_info']['code']}-w{week:02d}@powersemiotics.com"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;TZID=America/Guayaquil:{dt_start}",
            f"DTEND;TZID=America/Guayaquil:{dt_end}",
            f"SUMMARY:Sem {week:02d} - {title}",
            f"DESCRIPTION:Clase de {course_name}\\n\\nTema: {title}\\n\\nModulo Web Interactivo: {module_url}\\n\\nUbicacion: {location}",
            f"LOCATION:{location}",
            "STATUS:CONFIRMED",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")

    Path(output_ics).write_text("\r\n".join(lines), encoding='utf-8')
    print(f"[OK] Generado archivo de calendario individualizado: {output_ics} ({len(topics)} clases con temas especificos)")

if __name__ == "__main__":
    generate_ics("config/syllabi/2026-2/silabo_neurologia_v2.yaml", "docs/neurologia_semestre_2026_2.ics")
    generate_ics("config/syllabi/2026-2/silabo_gastroenterologia_v2.yaml", "docs/gastroenterologia_semestre_2026_2.ics")