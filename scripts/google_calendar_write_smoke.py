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
        default="NEURO",
        help="Course code (default: NEURO)",
    )
    parser.add_argument(
        "--date",
        default="2026-08-04",
        help="Class date YYYY-MM-DD (default: 2026-08-04)",
    )
    parser.add_argument(
        "--topic-title",
        default="Síndrome cerebeloso",
        help="Topic title for coaching briefing",
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
        help="Perform the actual write operation against Google Calendar API (Default: False / Dry Run)",
    )

    args = parser.parse_args()

    class_d = date.fromisoformat(args.date)
    tz = ZoneInfo(args.timezone)

    brief = CoachingBrief(
        semester_id=args.semester_id,
        course_code=args.course_code,
        class_date=class_d,
        topic_id="smoke-topic-1",
        topic_title=args.topic_title,
        learning_objectives=[
            "Reconocer los signos cardinales del síndrome cerebeloso.",
            "Diferenciar ataxia cerebelosa de ataxia sensitiva.",
        ],
        coaching_tips=[
            "Iniciar con examen de marcha y prueba índice-nariz.",
            "Hacer énfasis en dismetría y adiadococinesia.",
        ],
        teaching_questions=[
            "¿Cuál es el mecanismo fisiopatológico del temblor intencional?",
        ],
        common_pitfalls=[
            "Confundir dismetría con debilidad piramidal.",
        ],
        material_notes=[
            "Martillo de reflejos y diapasones.",
        ],
        assignment_note="Revisar caso clínico 3 en PowerSemiotics.",
        powersemiotics_url="https://powersemiotics.org/cases/cerebellar-1",
    )

    start_dt = datetime.combine(class_d, time(8, 0), tzinfo=tz)
    end_dt = datetime.combine(class_d, time(10, 0), tzinfo=tz)

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
        reminders_minutes=[15, 60],
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
