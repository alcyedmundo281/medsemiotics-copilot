#!/usr/bin/env python3
"""Derive the deterministic engine configuration from the official v2 syllabi.

The official syllabi (``config/syllabi/<semester>/silabo_*_v2.yaml``) are the single source
of truth for what is taught, on which date, and in which order. This script projects them
onto the three tracked files the engine actually reads:

* ``config/schedules/<semester>/<COURSE>.yaml`` -- the date-only baseline.
* ``config/syllabi/<semester>/<COURSE>.yaml`` -- the ordered topic plan.
* ``config/teaching_logs/<semester>/<COURSE>.yaml`` -- the sessions already delivered.

Only weeks the official syllabus marks ``completed`` are written to the teaching log, so the
next topic the engine proposes is always the first week that has not been taught yet.

Run ``python scripts/sync_syllabus_v2_to_config.py`` to rewrite the files, or pass
``--check`` to fail when the tracked files have drifted from the official syllabi.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_ROOT = REPO_ROOT / "config"
SEMESTER_ID = "2026-2"

OFFICIAL_SYLLABI: Mapping[str, str] = {
    "NEURO": "silabo_neurologia_v2.yaml",
    "GASTRO": "silabo_gastroenterologia_v2.yaml",
}

WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

COMPLETED_STATUS = "completed"

GENERATED_HEADER = (
    "# GENERATED FILE -- do not edit by hand.\n"
    "# Derived from config/syllabi/{semester}/{source} by scripts/sync_syllabus_v2_to_config.py.\n"
    "# Edit the official syllabus and re-run that script instead.\n"
)


class OfficialSyllabusError(RuntimeError):
    """Raised when an official syllabus cannot be projected onto the engine configuration."""


def _load_official(semester_id: str, source_name: str) -> dict[str, Any]:
    path = CONFIG_ROOT / "syllabi" / semester_id / source_name
    if not path.is_file():
        msg = f"Official syllabus not found: {path}"
        raise OfficialSyllabusError(msg)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"Official syllabus is not a mapping: {path}"
        raise OfficialSyllabusError(msg)
    for key in ("course_info", "schedule_18_weeks"):
        if key not in data:
            msg = f"Official syllabus {path} is missing the '{key}' section"
            raise OfficialSyllabusError(msg)
    return data


def _weeks(official: Mapping[str, Any]) -> list[dict[str, Any]]:
    weeks = sorted(official["schedule_18_weeks"], key=lambda item: int(item["week"]))
    seen_topics: set[str] = set()
    for week in weeks:
        topic_id = str(week["topic_id"])
        if topic_id in seen_topics:
            msg = f"Duplicate topic_id '{topic_id}' in the official syllabus"
            raise OfficialSyllabusError(msg)
        seen_topics.add(topic_id)
    return weeks


def _yaml_date(value: object) -> str:
    return date.fromisoformat(str(value)).isoformat()


def _quoted(value: object) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def render_schedule(course_code: str, official: Mapping[str, Any], source: str) -> str:
    """Render the date-only baseline schedule for one course."""
    info = official["course_info"]
    start = date.fromisoformat(str(info["start_date"]))
    weekday = WEEKDAY_NAMES[start.weekday()]
    lines = [
        GENERATED_HEADER.format(semester=SEMESTER_ID, source=source),
        "# Date-only baseline. Exact meeting times remain operational Calendar evidence.\n",
        f"semester_id: {_quoted(SEMESTER_ID)}\n",
        f"course_code: {_quoted(course_code)}\n",
        "enabled: true\n",
        f"teaching_start_date: {_quoted(start.isoformat())}\n",
        f"teaching_end_date: {_quoted(_yaml_date(info['end_date']))}\n",
        "meeting_rules:\n",
        f"  - weekday: {_quoted(weekday)}\n",
        "exceptions: []\n",
    ]
    return "".join(lines)


def render_syllabus(course_code: str, official: Mapping[str, Any], source: str) -> str:
    """Render the ordered topic plan for one course."""
    lines = [
        GENERATED_HEADER.format(semester=SEMESTER_ID, source=source),
        f"semester_id: {_quoted(SEMESTER_ID)}\n",
        f"course_code: {_quoted(course_code)}\n",
        "topics:\n",
    ]
    for week in _weeks(official):
        number = int(week["week"])
        lines.extend(
            [
                f"  - topic_id: {_quoted(week['topic_id'])}\n",
                f"    planned_order: {number}\n",
                f"    planned_week: {number}\n",
                "    required: true\n",
            ]
        )
    return "".join(lines)


def render_teaching_log(course_code: str, official: Mapping[str, Any], source: str) -> str:
    """Render the delivered sessions for one course.

    A week reaches the teaching log only once the official syllabus marks it ``completed``.
    """
    prefix = course_code.lower()
    lines = [
        GENERATED_HEADER.format(semester=SEMESTER_ID, source=source),
        "# Sessions the official syllabus reports as delivered. Weeks still marked active or\n",
        "# projected are absent on purpose: the engine proposes the first week not taught yet.\n",
        f"semester_id: {_quoted(SEMESTER_ID)}\n",
        f"course_code: {_quoted(course_code)}\n",
        "sessions:\n",
    ]
    delivered = [week for week in _weeks(official) if str(week["status"]) == COMPLETED_STATUS]
    if not delivered:
        return "".join(lines[:-1]) + "sessions: []\n"
    for sequence, week in enumerate(delivered, start=1):
        number = int(week["week"])
        lines.extend(
            [
                f"  - session_id: {_quoted(f'{prefix}-{SEMESTER_ID}-w{number:02d}')}\n",
                f"    semester_id: {_quoted(SEMESTER_ID)}\n",
                f"    course_code: {_quoted(course_code)}\n",
                f"    session_date: {_quoted(_yaml_date(week['date']))}\n",
                f"    sequence_number: {sequence}\n",
                f"    notes: {_quoted(f'Week {number:02d} of the official syllabus.')}\n",
                "    topics:\n",
                f"      - topic_id: {_quoted(week['topic_id'])}\n",
                '        status: "completed"\n',
                f"        notes: {_quoted(week['title'])}\n",
            ]
        )
    return "".join(lines)


def rendered_files(semester_id: str = SEMESTER_ID) -> dict[Path, str]:
    """Render every tracked engine file derived from the official syllabi."""
    rendered: dict[Path, str] = {}
    for course_code, source in OFFICIAL_SYLLABI.items():
        official = _load_official(semester_id, source)
        rendered[CONFIG_ROOT / "schedules" / semester_id / f"{course_code}.yaml"] = render_schedule(
            course_code, official, source
        )
        rendered[CONFIG_ROOT / "syllabi" / semester_id / f"{course_code}.yaml"] = render_syllabus(
            course_code, official, source
        )
        rendered[CONFIG_ROOT / "teaching_logs" / semester_id / f"{course_code}.yaml"] = (
            render_teaching_log(course_code, official, source)
        )
    return rendered


def _drifted(rendered: Mapping[Path, str]) -> list[Path]:
    drifted: list[Path] = []
    for path, content in rendered.items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != content:
            drifted.append(path)
    return drifted


def _write(rendered: Mapping[Path, str]) -> Iterable[Path]:
    for path, content in sorted(rendered.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        yield path


def main(argv: list[str] | None = None) -> int:
    """Rewrite (or verify) the engine configuration derived from the official syllabi."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when a tracked file differs from the official syllabi.",
    )
    args = parser.parse_args(argv)

    rendered = rendered_files()
    if args.check:
        drifted = _drifted(rendered)
        for path in drifted:
            print(f"[drift] {path.relative_to(REPO_ROOT)}")
        if drifted:
            print("Run 'python scripts/sync_syllabus_v2_to_config.py' to regenerate.")
            return 1
        print(f"[ok] {len(rendered)} tracked files match the official syllabi.")
        return 0

    for path in _write(rendered):
        print(f"[written] {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
