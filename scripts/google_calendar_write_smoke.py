"""Interactive CLI smoke tool for Google Calendar write operations.

SAFETY:
This script performs a DRY RUN by default and will NEVER write to Google Calendar
unless the --execute flag is explicitly supplied.
"""

import argparse
import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

# Add src to sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from medsemiotics.domain.coaching import CalendarPublishRequest, CoachingBrief
from medsemiotics.domain.constants import (
    MANAGED_TRUE_VALUE,
    PROP_CLASS_DATE,
    PROP_COURSE_CODE,
    PROP_MANAGED,
    PROP_SCHEMA_VERSION,
    PROP_SEMESTER_ID,
    PROP_TOPIC_ID,
    SCHEMA_VERSION_VALUE,
)
from medsemiotics.integrations.google_calendar.writer import GoogleCalendarWriter
from medsemiotics.services.coaching_formatter import (
    build_teaching_event_title,
    format_coaching_brief,
)

stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if stdout_reconfigure is not None:
    stdout_reconfigure(encoding="utf-8")


def main() -> None:
    """Entry point for Google Calendar write smoke script."""
    parser = argparse.ArgumentParser(
        description="MedSemiotics Google Calendar Write Integration Smoke Test (Dry Run by default)"
    )
    parser.add_argument(
        "--calendar-id",
        required=True,
        help="Target Google Calendar ID",
    )
    parser.add_argument(
        "--semester-id",
        default="2026-2",
        help="Semester identifier (default: 2026-2)",
    )
    parser.add_argument(
        "--course-code",
        default="TEST",
        help="Course code (default: TEST)",
    )
    parser.add_argument(
        "--date",
        default="2026-09-01",
        help="Class date YYYY-MM-DD (default: 2026-09-01)",
    )
    parser.add_argument(
        "--topic-title",
        default="Calendar Integration Test",
        help="Topic title for coaching briefing",
    )
    parser.add_argument(
        "--start-time",
        default="18:00",
        help="Local event start time HH:MM (default: 18:00)",
    )
    parser.add_argument(
        "--end-time",
        default="18:15",
        help="Local event end time HH:MM (default: 18:15)",
    )
    parser.add_argument(
        "--timezone",
        default="America/Guayaquil",
        help="Academic timezone (default: America/Guayaquil)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Perform actual write against Google Calendar API (Default: False / Dry Run)",
    )

    args = parser.parse_args()

    class_d = date.fromisoformat(args.date)
    tz = ZoneInfo(args.timezone)
    start_time = time.fromisoformat(args.start_time)
    end_time = time.fromisoformat(args.end_time)
    if start_time >= end_time:
        parser.error("--start-time must be earlier than --end-time")

    brief = CoachingBrief(
        semester_id=args.semester_id,
        course_code=args.course_code,
        class_date=class_d,
        topic_id="calendar-integration-test",
        topic_title=args.topic_title,
        learning_objectives=[
            "Verificar la publicación controlada de un evento de prueba.",
        ],
        coaching_tips=[
            "Este contenido es técnico y no representa una clase real.",
        ],
        teaching_questions=[
            "¿El segundo intento conserva el mismo evento administrado?",
        ],
        common_pitfalls=[
            "Usar un código de curso productivo durante una prueba de integración.",
        ],
        material_notes=[
            "Evento TEST sin asistentes, videollamada ni adjuntos.",
        ],
        assignment_note=None,
        powersemiotics_url=None,
    )

    start_dt = datetime.combine(class_d, start_time, tzinfo=tz)
    end_dt = datetime.combine(class_d, end_time, tzinfo=tz)

    title = build_teaching_event_title(
        course_code=brief.course_code,
        topic_title=brief.topic_title,
    )
    description = format_coaching_brief(brief)

    metadata = {
        PROP_MANAGED: MANAGED_TRUE_VALUE,
        PROP_SEMESTER_ID: brief.semester_id,
        PROP_COURSE_CODE: brief.course_code,
        PROP_CLASS_DATE: brief.class_date.isoformat(),
        PROP_SCHEMA_VERSION: SCHEMA_VERSION_VALUE,
        PROP_TOPIC_ID: brief.topic_id or "",
    }

    publish_req = CalendarPublishRequest(
        calendar_id=args.calendar_id,
        event_date=class_d,
        start=start_dt,
        end=end_dt,
        title=title,
        description=description,
        location=None,
        reminders_minutes=[10],
        metadata=metadata,
    )

    print("==================================================")
    print("MEDSEMIOTICS GOOGLE CALENDAR PUBLISH SMOKE TEST")
    print("==================================================")
    print(f"Calendar ID : {publish_req.calendar_id}")
    print(f"Event Date  : {publish_req.event_date}")
    print(f"Start Time  : {publish_req.start}")
    print(f"End Time    : {publish_req.end}")
    print(f"Title       : {publish_req.title}")
    print(f"Reminders   : {publish_req.reminders_minutes} min")
    print("\n--- Description ---")
    print(publish_req.description)
    print("-------------------")
    print(f"Metadata    : {publish_req.metadata}")
    print("==================================================")

    if not args.execute:
        print("\n[DRY RUN MODE] No changes were made to Google Calendar.")
        print("To execute this write, run with --execute.")
        return

    print("\n[EXECUTE MODE] Initializing GoogleCalendarWriter...")
    writer = GoogleCalendarWriter(interactive=True)
    result = writer.publish(publish_req)
    print("\n>>> PUBLISH SUCCESSFUL <<<")
    print(f"Action   : {result.action.value}")
    print(f"Event ID : {result.event_id}")


if __name__ == "__main__":
    main()
