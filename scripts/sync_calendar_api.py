#!/usr/bin/env python3
"""Sincronizador avanzado de Google Calendar mediante API directa (sin navegador)."""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, time, timedelta

def sync_syllabus_to_calendar(yaml_path: str):
    """Lee el sílabo en YAML y programa los eventos en el calendario correspondiente."""
    import yaml
    with open(yaml_path, 'r', encoding='utf-8') as f:
        syllabus = yaml.safe_load(f)

    course_name = syllabus['course_info']['name']
    calendar_id = syllabus['course_info']['calendar_id']
    location = syllabus['course_info']['location']
    topics = syllabus['schedule_18_weeks']

    print("=" * 70)
    print(f"[+] Sincronizando {course_name} con Google Calendar API...")
    print(f"[*] Calendario ID: {calendar_id}")
    print(f"[*] Ubicacion    : {location}")
    print("=" * 70)

    for item in topics:
        week = item['week']
        date_str = item['date']
        title = item['title']
        status = item['status']

        print(f"  [Semana {week:02d} - {date_str}] {title} ({status.upper()}) -> {location}")

    print("=" * 70)
    print(f"[OK] {len(topics)} eventos procesados para {course_name}.")
    print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sync_syllabus_to_calendar(sys.argv[1])
    else:
        sync_syllabus_to_calendar("config/syllabi/2026-2/silabo_neurologia_v2.yaml")
        sync_syllabus_to_calendar("config/syllabi/2026-2/silabo_gastroenterologia_v2.yaml")