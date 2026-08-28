"""Unit tests for calendar event filtering service."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.domain.calendar import OperationalCalendarEvent
from medsemiotics.services.calendar_filter import filter_course_calendar_events


class TestCalendarFilter:
    """Test suite for filter_course_calendar_events."""

    @pytest.fixture
    def sample_events(self) -> list[OperationalCalendarEvent]:
        tz = ZoneInfo("America/Lima")
        return [
            OperationalCalendarEvent(
                event_id="e1",
                calendar_id="cal_1",
                title="Clase de Neurología Clínica - Sesión 1",
                start=datetime(2026, 8, 4, 10, 0, tzinfo=tz),
                end=datetime(2026, 8, 4, 12, 0, tzinfo=tz),
                all_day=False,
            ),
            OperationalCalendarEvent(
                event_id="e2",
                calendar_id="cal_1",
                title="Seminario de Gastroenterología",
                start=datetime(2026, 8, 5, 14, 0, tzinfo=tz),
                end=datetime(2026, 8, 5, 16, 0, tzinfo=tz),
                all_day=False,
            ),
            OperationalCalendarEvent(
                event_id="e3",
                calendar_id="cal_1",
                title="neuro - repaso examen",
                start=datetime(2026, 8, 11, 10, 0, tzinfo=tz),
                end=datetime(2026, 8, 11, 12, 0, tzinfo=tz),
                all_day=False,
            ),
            OperationalCalendarEvent(
                event_id="e4",
                calendar_id="cal_1",
                title="Reunión de Departamento de Medicina",
                start=datetime(2026, 8, 6, 9, 0, tzinfo=tz),
                end=datetime(2026, 8, 6, 10, 0, tzinfo=tz),
                all_day=False,
            ),
        ]

    def test_filter_matching_aliases(self, sample_events: list[OperationalCalendarEvent]) -> None:
        """Verify matching aliases select correct events case-insensitively with Unicode support."""
        aliases = ["Neurología", "Neurologia", "NEURO"]
        filtered = filter_course_calendar_events(
            sample_events,
            course_code="NEURO",
            aliases=aliases,
        )

        assert len(filtered) == 2
        assert [e.event_id for e in filtered] == ["e1", "e3"]

    def test_filter_gastro_matching(self, sample_events: list[OperationalCalendarEvent]) -> None:
        """Verify GASTRO aliases isolate only the gastroenterology event."""
        aliases = ["Gastroenterología", "GASTRO"]
        filtered = filter_course_calendar_events(
            sample_events,
            course_code="GASTRO",
            aliases=aliases,
        )

        assert len(filtered) == 1
        assert filtered[0].event_id == "e2"

    def test_filter_no_matches(self, sample_events: list[OperationalCalendarEvent]) -> None:
        """Verify unrelated alias returns empty list."""
        filtered = filter_course_calendar_events(
            sample_events,
            course_code="CARDIO",
            aliases=["Cardiología", "CARDIO"],
        )
        assert filtered == []

    def test_filter_empty_aliases_returns_empty(
        self, sample_events: list[OperationalCalendarEvent]
    ) -> None:
        """Verify empty aliases list returns empty list."""
        filtered = filter_course_calendar_events(
            sample_events,
            course_code="NEURO",
            aliases=[],
        )
        assert filtered == []
