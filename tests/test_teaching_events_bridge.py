"""Tests for the teaching-events bridge consumed by secretario-clinico."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from medsemiotics.services.teaching_events_bridge import (
    BRIDGE_SCHEMA,
    TeachingBridgeError,
    build_bridge_document,
    build_bridge_events,
    event_id_for,
    render_bridge_document,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SYLLABUS_DIR = REPO_ROOT / "config" / "syllabi" / "2026-2"


def _syllabus(weeks: list[dict[str, Any]], code: str = "NEURO") -> dict[str, Any]:
    return {
        "course_info": {
            "name": "Cátedra de prueba",
            "code": code,
            "semester": "2026-2",
            "location": "Aula de Administración",
            "web_hub": "https://example.org/hub.html",
        },
        "schedule_18_weeks": weeks,
    }


def _week(number: int, date: str, topic: str, **extra: Any) -> dict[str, Any]:
    return {
        "week": number,
        "date": date,
        "topic_id": topic,
        "title": topic.title(),
        "status": "projected",
        **extra,
    }


def test_event_id_depends_only_on_semester_course_and_week() -> None:
    assert event_id_for("2026-2", "NEURO", 4) == "medsemiotics-2026-2-NEURO-w04"


def test_reprogrammed_week_keeps_its_identifier() -> None:
    before = build_bridge_events(_syllabus([_week(14, "2026-09-22", "epilepsia")]))
    after = build_bridge_events(_syllabus([_week(14, "2026-09-22", "desmielinizantes")]))

    assert before[0].event_id == after[0].event_id
    assert before[0].title != after[0].title


def test_events_carry_local_times_and_fallback_module() -> None:
    event = build_bridge_events(_syllabus([_week(1, "2026-06-23", "intro")]))[0]

    assert (event.start_local, event.end_local) == ("16:00", "17:30")
    assert event.web_module == "https://example.org/hub.html"
    assert event.title == "Sem 01 - Intro"


def test_week_module_overrides_hub() -> None:
    week = _week(2, "2026-06-30", "estado", web_module="https://example.org/m.html")
    assert build_bridge_events(_syllabus([week]))[0].web_module == "https://example.org/m.html"


def test_missing_section_is_rejected() -> None:
    with pytest.raises(TeachingBridgeError):
        build_bridge_events({"course_info": {}})


def test_semester_mismatch_is_rejected() -> None:
    with pytest.raises(TeachingBridgeError):
        build_bridge_document("2027-1", [_syllabus([_week(1, "2026-06-23", "a")])], [])


def test_duplicate_identifiers_are_rejected() -> None:
    syllabus = _syllabus([_week(1, "2026-06-23", "a")])
    with pytest.raises(TeachingBridgeError):
        build_bridge_document("2026-2", [syllabus, syllabus], [])


def test_document_is_deterministic_and_sorted() -> None:
    neuro = _syllabus([_week(2, "2026-06-30", "b"), _week(1, "2026-06-23", "a")])
    gastro = _syllabus([_week(1, "2026-06-24", "c")], code="GASTRO")

    first = render_bridge_document(build_bridge_document("2026-2", [neuro, gastro], ["x"]))
    second = render_bridge_document(build_bridge_document("2026-2", [gastro, neuro], ["x"]))

    assert first == second
    document = json.loads(first)
    assert document["schema"] == BRIDGE_SCHEMA
    assert document["owner_of_calendar_writes"] == "secretario-clinico"
    assert [event["date"] for event in document["events"]] == [
        "2026-06-23",
        "2026-06-24",
        "2026-06-30",
    ]


def test_real_syllabi_produce_36_unique_classes() -> None:
    syllabi = [
        yaml.safe_load((SYLLABUS_DIR / name).read_text(encoding="utf-8"))
        for name in ("silabo_neurologia_v2.yaml", "silabo_gastroenterologia_v2.yaml")
    ]
    document = build_bridge_document("2026-2", syllabi, [])

    assert len(document["events"]) == 36
    assert len({event["event_id"] for event in document["events"]}) == 36
