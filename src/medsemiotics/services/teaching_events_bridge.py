"""Bridge contract that hands the teaching schedule to secretario-clinico.

MedSemiotics no longer writes to the instructor's calendar. It derives one deterministic JSON
document per semester from the official syllabi, and secretario-clinico imports it into the
clinical agenda, which owns every Google Calendar write.

Each class carries an ``event_id`` that depends only on semester, course and week. A reprogrammed
class therefore keeps its identifier and changes its fields, so the consumer updates the existing
entry instead of adding a duplicate. The document has no generation timestamp, so an unchanged
syllabus always produces byte-identical output.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

BRIDGE_SCHEMA = "medsemiotics.teaching-events/v1"
BRIDGE_TIMEZONE = "America/Guayaquil"
CLASS_START_LOCAL = "16:00"
CLASS_DURATION = timedelta(minutes=90)


class TeachingBridgeError(ValueError):
    """Raised when an official syllabus cannot be turned into bridge events."""


@dataclass(frozen=True)
class TeachingBridgeEvent:
    """One class of the official syllabus, as secretario-clinico consumes it."""

    event_id: str
    semester_id: str
    course_code: str
    course_name: str
    week: int
    topic_id: str
    title: str
    date: str
    start_local: str
    end_local: str
    location: str
    web_module: str
    status: str


def event_id_for(semester_id: str, course_code: str, week: int) -> str:
    """Return the stable identifier of a syllabus week, independent of its date."""
    return f"medsemiotics-{semester_id}-{course_code}-w{week:02d}"


def _end_local(date: str, start_local: str) -> str:
    start = datetime.strptime(f"{date} {start_local}", "%Y-%m-%d %H:%M")
    return (start + CLASS_DURATION).strftime("%H:%M")


def build_bridge_events(syllabus: Mapping[str, Any]) -> list[TeachingBridgeEvent]:
    """Derive the bridge events of one official syllabus, ordered by week."""
    try:
        info = syllabus["course_info"]
        weeks = syllabus["schedule_18_weeks"]
        course_code = str(info["code"])
        semester_id = str(info["semester"])
    except (KeyError, TypeError) as error:
        msg = f"Official syllabus is missing a required section: {error}"
        raise TeachingBridgeError(msg) from error

    default_module = str(info.get("web_hub", ""))
    events: list[TeachingBridgeEvent] = []
    for week in sorted(weeks, key=lambda item: int(item["week"])):
        number = int(week["week"])
        date = str(week["date"])
        events.append(
            TeachingBridgeEvent(
                event_id=event_id_for(semester_id, course_code, number),
                semester_id=semester_id,
                course_code=course_code,
                course_name=str(info["name"]),
                week=number,
                topic_id=str(week["topic_id"]),
                title=f"Sem {number:02d} - {week['title']}",
                date=date,
                start_local=CLASS_START_LOCAL,
                end_local=_end_local(date, CLASS_START_LOCAL),
                location=str(info.get("location", "")),
                web_module=str(week.get("web_module", default_module)),
                status=str(week["status"]),
            )
        )
    return events


def build_bridge_document(
    semester_id: str, syllabi: Iterable[Mapping[str, Any]], sources: Iterable[str]
) -> dict[str, Any]:
    """Assemble the full bridge document for one semester from several syllabi."""
    events: list[TeachingBridgeEvent] = []
    for syllabus in syllabi:
        course_events = build_bridge_events(syllabus)
        mismatched = {event.semester_id for event in course_events} - {semester_id}
        if mismatched:
            msg = f"Syllabus semester {sorted(mismatched)} does not match {semester_id}."
            raise TeachingBridgeError(msg)
        events.extend(course_events)

    identifiers = [event.event_id for event in events]
    if len(identifiers) != len(set(identifiers)):
        msg = "Bridge events must have unique identifiers."
        raise TeachingBridgeError(msg)

    events.sort(key=lambda event: (event.date, event.course_code, event.week))
    return {
        "schema": BRIDGE_SCHEMA,
        "semester_id": semester_id,
        "timezone": BRIDGE_TIMEZONE,
        "owner_of_calendar_writes": "secretario-clinico",
        "sources": sorted(sources),
        "events": [asdict(event) for event in events],
    }


def render_bridge_document(document: Mapping[str, Any]) -> str:
    """Serialize the bridge document deterministically."""
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
