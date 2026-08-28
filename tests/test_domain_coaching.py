"""Unit tests for coaching brief and calendar publish domain models."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from medsemiotics.domain.coaching import (
    CalendarPublishAction,
    CalendarPublishRequest,
    CalendarPublishResult,
    CoachingBrief,
    ManagedCalendarEvent,
)


class TestCoachingBrief:
    """Test suite for CoachingBrief domain model."""

    def test_valid_coaching_brief(self) -> None:
        """Verify creating a valid CoachingBrief model."""
        brief = CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
            topic_id="topic-1",
            topic_title="Síndrome cerebeloso",
            learning_objectives=["Reconocer signos cardinales."],
            coaching_tips=["Iniciar con marcha."],
            teaching_questions=["¿Qué es la ataxia?"],
            common_pitfalls=["Confundir ataxia con paresia."],
            material_notes=["Martillo de reflejos."],
            assignment_note="Caso 1.",
            powersemiotics_url="https://powersemiotics.org/cases/1",
        )
        assert brief.semester_id == "2026-2"
        assert brief.course_code == "NEURO"
        assert brief.topic_title == "Síndrome cerebeloso"
        assert brief.powersemiotics_url == "https://powersemiotics.org/cases/1"

    def test_identifier_normalization(self) -> None:
        """Verify course code and semester id normalization."""
        brief = CoachingBrief(
            semester_id=" 2026-2 ",
            course_code="neuro",
            class_date=date(2026, 8, 4),
            topic_title="Examen neurológico",
        )
        assert brief.semester_id == "2026-2"
        assert brief.course_code == "NEURO"

    def test_empty_topic_title_rejected(self) -> None:
        """Verify empty or whitespace topic title raises ValidationError."""
        with pytest.raises(ValidationError, match="topic_title must not be empty"):
            CoachingBrief(
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 8, 4),
                topic_title="   ",
            )

    def test_blank_list_items_rejected(self) -> None:
        """Verify blank items in lists raise ValidationError."""
        with pytest.raises(ValidationError, match="must not be empty"):
            CoachingBrief(
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 8, 4),
                topic_title="Valid Title",
                learning_objectives=["Valid objective", "   "],
            )

    @pytest.mark.parametrize(
        "invalid_url",
        ["ftp://example.com", "not_a_url", "http://", "https:///path"],
    )
    def test_invalid_url_rejected(self, invalid_url: str) -> None:
        """Verify invalid URL schemes or missing hosts raise ValidationError."""
        with pytest.raises(ValidationError, match="Invalid URL"):
            CoachingBrief(
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 8, 4),
                topic_title="Valid Title",
                powersemiotics_url=invalid_url,
            )

    def test_blank_optional_url_normalizes_to_none(self) -> None:
        """Verify empty string for optional URL normalizes to None."""
        brief = CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
            topic_title="Valid Title",
            powersemiotics_url="   ",
        )
        assert brief.powersemiotics_url is None


class TestCalendarPublishRequest:
    """Test suite for CalendarPublishRequest domain model."""

    @pytest.fixture
    def guayaquil_tz(self) -> ZoneInfo:
        return ZoneInfo("America/Guayaquil")

    def test_valid_publish_request(self, guayaquil_tz: ZoneInfo) -> None:
        """Verify creating a valid CalendarPublishRequest."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)

        req = CalendarPublishRequest(
            calendar_id="cal_123",
            event_date=date(2026, 8, 4),
            start=start,
            end=end,
            title="NEURO — Síndrome cerebeloso",
            description="Brief description",
            location="Aula 402",
            reminders_minutes=[60, 15, 60],  # test deduplication
            metadata={"medsemiotics_managed": "true"},
        )
        assert req.calendar_id == "cal_123"
        assert req.reminders_minutes == [15, 60]
        assert req.location == "Aula 402"

    def test_naive_datetime_rejected(self) -> None:
        """Verify naive start/end datetime raises ValidationError."""
        with pytest.raises(ValidationError, match="must be timezone-aware"):
            CalendarPublishRequest(
                calendar_id="cal_123",
                event_date=date(2026, 8, 4),
                start=datetime(2026, 8, 4, 8, 0),  # Naive!
                end=datetime(2026, 8, 4, 10, 0),
                title="Title",
                description="Desc",
                metadata={},
            )

    def test_start_greater_or_equal_end_rejected(self, guayaquil_tz: ZoneInfo) -> None:
        """Verify start >= end raises ValidationError."""
        start = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)

        with pytest.raises(ValidationError, match="must be strictly before end"):
            CalendarPublishRequest(
                calendar_id="cal_123",
                event_date=date(2026, 8, 4),
                start=start,
                end=end,
                title="Title",
                description="Desc",
                metadata={},
            )

    def test_event_date_mismatch_with_start_rejected(self, guayaquil_tz: ZoneInfo) -> None:
        """Verify event_date not matching start.date() raises ValidationError."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)

        with pytest.raises(ValidationError, match="does not match start timestamp date"):
            CalendarPublishRequest(
                calendar_id="cal_123",
                event_date=date(2026, 8, 5),  # Mismatch!
                start=start,
                end=end,
                title="Title",
                description="Desc",
                metadata={},
            )

    @pytest.mark.parametrize(
        "invalid_reminder",
        [-5, 0, 50000],  # 50000 exceeds 4 weeks (40320)
    )
    def test_invalid_reminder_bounds_rejected(
        self, guayaquil_tz: ZoneInfo, invalid_reminder: int
    ) -> None:
        """Verify non-positive or overly large reminder values raise ValidationError."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)

        with pytest.raises(ValidationError, match="Reminder minute"):
            CalendarPublishRequest(
                calendar_id="cal_123",
                event_date=date(2026, 8, 4),
                start=start,
                end=end,
                title="Title",
                description="Desc",
                reminders_minutes=[invalid_reminder],
                metadata={},
            )


class TestManagedCalendarEventAndResult:
    """Test suite for ManagedCalendarEvent and CalendarPublishResult."""

    def test_publish_result_creation(self) -> None:
        """Verify creating CalendarPublishResult."""
        res = CalendarPublishResult(
            calendar_id="cal_1",
            event_id="evt_1",
            action=CalendarPublishAction.CREATED,
        )
        assert res.action == CalendarPublishAction.CREATED
        assert res.event_id == "evt_1"

    def test_managed_calendar_event_creation(self) -> None:
        """Verify creating ManagedCalendarEvent."""
        tz = ZoneInfo("UTC")
        event = ManagedCalendarEvent(
            calendar_id="cal_1",
            event_id="evt_1",
            title="NEURO — Clase",
            description="Description",
            start=datetime(2026, 8, 4, 8, 0, tzinfo=tz),
            end=datetime(2026, 8, 4, 10, 0, tzinfo=tz),
            reminders_minutes=[15, 30],
            metadata={"medsemiotics_managed": "true"},
        )
        assert event.event_id == "evt_1"
        assert event.reminders_minutes == [15, 30]
        assert event.metadata["medsemiotics_managed"] == "true"
