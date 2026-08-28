"""Deterministic filtering service for matching calendar events to courses by alias."""

import unicodedata
from collections.abc import Collection

from medsemiotics.domain.calendar import OperationalCalendarEvent


def _normalize_str(text: str) -> str:
    """Normalize string using Unicode NFKC form and lowercasing."""
    return unicodedata.normalize("NFKC", text).lower()


def filter_course_calendar_events(
    events: Collection[OperationalCalendarEvent],
    *,
    course_code: str,  # noqa: ARG001
    aliases: Collection[str],
) -> list[OperationalCalendarEvent]:
    """Filter operational calendar events that match any of the provided course aliases.

    Args:
        events: Collection of OperationalCalendarEvent instances to inspect.
        course_code: The target course identifier (e.g. 'NEURO').
        aliases: Non-empty collection of string aliases to match against the event title.

    Returns:
        List of matching OperationalCalendarEvent objects, sorted by start and event_id.
    """
    if not aliases:
        return []

    normalized_aliases = [_normalize_str(alias) for alias in aliases if alias.strip()]
    if not normalized_aliases:
        return []

    matched: list[OperationalCalendarEvent] = []

    for event in events:
        norm_title = _normalize_str(event.title)
        if any(norm_alias in norm_title for norm_alias in normalized_aliases):
            matched.append(event)

    return sorted(matched, key=lambda e: (e.start, e.event_id))
