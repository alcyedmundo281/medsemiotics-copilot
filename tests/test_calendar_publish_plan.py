"""Unit tests for building calendar publish requests."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.domain.coaching import CoachingBrief
from medsemiotics.domain.constants import (
    MANAGED_TRUE_VALUE,
    PROP_CLASS_DATE,
    PROP_COURSE_CODE,
    PROP_MANAGED,
    PROP_SCHEMA_VERSION,
    PROP_SEMESTER_ID,
    PROP_TOPIC_ID,
)
from medsemiotics.domain.effective_schedule import (
    EffectiveClassEvent,
    EffectiveClassSource,
    EffectiveClassStatus,
)
from medsemiotics.domain.exceptions import CalendarPublishPlanError
from medsemiotics.services.calendar_publish_plan import (
    build_calendar_publish_request,
)


class TestCalendarPublishPlan:
    """Test suite for build_calendar_publish_request."""

    @pytest.fixture
    def guayaquil_tz(self) -> ZoneInfo:
        return ZoneInfo("America/Guayaquil")

    @pytest.fixture
    def sample_brief(self) -> CoachingBrief:
        return CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
            topic_id="t_cerebelo",
            topic_title="Síndrome cerebeloso",
            learning_objectives=["Reconocer signos."],
        )

    def test_scheduled_class_builds_valid_request(
        self, guayaquil_tz: ZoneInfo, sample_brief: CoachingBrief
    ) -> None:
        """Verify scheduled class builds valid request with ownership metadata."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)

        event = EffectiveClassEvent(
            date=date(2026, 8, 4),
            semester_id="2026-2",
            course_code="NEURO",
            source=EffectiveClassSource.BASELINE,
            status=EffectiveClassStatus.SCHEDULED,
            start=start,
            end=end,
        )

        req = build_calendar_publish_request(
            calendar_id="cal_neuro",
            semester_timezone=guayaquil_tz,
            class_event=event,
            brief=sample_brief,
            reminders_minutes=[15, 60],
        )

        assert req.calendar_id == "cal_neuro"
        assert req.event_date == date(2026, 8, 4)
        assert req.title == "NEURO — Síndrome cerebeloso"
        assert req.start == start
        assert req.end == end
        assert req.reminders_minutes == [15, 60]
        assert req.metadata[PROP_MANAGED] == MANAGED_TRUE_VALUE
        assert req.metadata[PROP_SEMESTER_ID] == "2026-2"
        assert req.metadata[PROP_COURSE_CODE] == "NEURO"
        assert req.metadata[PROP_CLASS_DATE] == "2026-08-04"
        assert req.metadata[PROP_SCHEMA_VERSION] == "1"
        assert req.metadata[PROP_TOPIC_ID] == "t_cerebelo"

    def test_cancelled_class_rejected(
        self, guayaquil_tz: ZoneInfo, sample_brief: CoachingBrief
    ) -> None:
        """Verify cancelled class raises CalendarPublishPlanError."""
        event = EffectiveClassEvent(
            date=date(2026, 8, 4),
            semester_id="2026-2",
            course_code="NEURO",
            source=EffectiveClassSource.BASELINE_AND_CALENDAR,
            status=EffectiveClassStatus.CANCELLED,
            start=datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz),
            end=datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz),
        )

        with pytest.raises(CalendarPublishPlanError, match="Cannot publish coaching brief for cancelled class"):
            build_calendar_publish_request(
                calendar_id="cal_neuro",
                semester_timezone=guayaquil_tz,
                class_event=event,
                brief=sample_brief,
            )

    def test_missing_start_end_times_rejected(
        self, guayaquil_tz: ZoneInfo, sample_brief: CoachingBrief
    ) -> None:
        """Verify class event without timestamps raises CalendarPublishPlanError."""
        event = EffectiveClassEvent(
            date=date(2026, 8, 4),
            semester_id="2026-2",
            course_code="NEURO",
            source=EffectiveClassSource.BASELINE,
            status=EffectiveClassStatus.SCHEDULED,
            start=None,
            end=None,
        )

        with pytest.raises(CalendarPublishPlanError, match="does not contain start/end timestamps"):
            build_calendar_publish_request(
                calendar_id="cal_neuro",
                semester_timezone=guayaquil_tz,
                class_event=event,
                brief=sample_brief,
            )

    def test_scope_mismatch_rejected(
        self, guayaquil_tz: ZoneInfo, sample_brief: CoachingBrief
    ) -> None:
        """Verify scope mismatch between class event and brief raises CalendarPublishPlanError."""
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)

        event = EffectiveClassEvent(
            date=date(2026, 8, 4),
            semester_id="2026-2",
            course_code="GASTRO",  # Mismatch!
            source=EffectiveClassSource.BASELINE,
            status=EffectiveClassStatus.SCHEDULED,
            start=start,
            end=end,
        )

        with pytest.raises(CalendarPublishPlanError, match="Scope mismatch"):
            build_calendar_publish_request(
                calendar_id="cal_gastro",
                semester_timezone=guayaquil_tz,
                class_event=event,
                brief=sample_brief,
            )
