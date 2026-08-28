"""Unit tests for CalendarCoachingService orchestration and authorization gates."""

from datetime import date, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from medsemiotics.domain.academic import Course, SemesterConfig
from medsemiotics.domain.calendar import CourseCalendarConfig
from medsemiotics.domain.coaching import (
    CalendarPublishAction,
    CalendarPublishResult,
    CoachingBrief,
)
from medsemiotics.domain.effective_schedule import (
    EffectiveClassEvent,
    EffectiveClassSource,
    EffectiveClassStatus,
    EffectiveTeachingSchedule,
)
from medsemiotics.domain.exceptions import (
    CalendarConfigError,
    CalendarPublishPlanError,
    CalendarWriteAuthorizationError,
)
from medsemiotics.integrations.google_calendar.writer import GoogleCalendarWriter
from medsemiotics.services.calendar_coaching_service import (
    CalendarCoachingService,
)
from medsemiotics.services.calendar_config_repository import (
    CalendarConfigRepository,
)
from medsemiotics.services.effective_schedule_service import (
    EffectiveScheduleService,
)
from medsemiotics.services.semester_repository import SemesterRepository


class TestCalendarCoachingService:
    """Test suite for CalendarCoachingService."""

    @pytest.fixture
    def guayaquil_tz(self) -> ZoneInfo:
        return ZoneInfo("America/Guayaquil")

    @pytest.fixture
    def mock_semester_repo(self) -> MagicMock:
        repo = MagicMock(spec=SemesterRepository)
        repo.get.return_value = SemesterConfig(
            semester_id="2026-2",
            display_name="2026-2",
            active=True,
            timezone="America/Guayaquil",
            courses=[Course(code="NEURO", name="Neurología")],
        )
        return repo

    @pytest.fixture
    def mock_calendar_config_repo(self) -> MagicMock:
        repo = MagicMock(spec=CalendarConfigRepository)
        repo.get.return_value = CourseCalendarConfig(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=True,
            calendar_id="cal_neuro",
            aliases=["NEURO"],
        )
        return repo

    @pytest.fixture
    def mock_effective_schedule_service(self, guayaquil_tz: ZoneInfo) -> MagicMock:
        service = MagicMock(spec=EffectiveScheduleService)
        start = datetime(2026, 8, 4, 8, 0, tzinfo=guayaquil_tz)
        end = datetime(2026, 8, 4, 10, 0, tzinfo=guayaquil_tz)
        service.get_effective_schedule.return_value = EffectiveTeachingSchedule(
            semester_id="2026-2",
            course_code="NEURO",
            timezone="America/Guayaquil",
            events=[
                EffectiveClassEvent(
                    date=date(2026, 8, 4),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE,
                    status=EffectiveClassStatus.SCHEDULED,
                    start=start,
                    end=end,
                ),
                EffectiveClassEvent(
                    date=date(2026, 8, 11),
                    semester_id="2026-2",
                    course_code="NEURO",
                    source=EffectiveClassSource.BASELINE_AND_CALENDAR,
                    status=EffectiveClassStatus.CANCELLED,
                    start=start.replace(day=11),
                    end=end.replace(day=11),
                ),
            ],
        )
        return service

    @pytest.fixture
    def mock_writer(self) -> MagicMock:
        writer = MagicMock(spec=GoogleCalendarWriter)
        writer.publish.return_value = CalendarPublishResult(
            calendar_id="cal_neuro",
            event_id="published_evt_1",
            action=CalendarPublishAction.CREATED,
        )
        return writer

    @pytest.fixture
    def coaching_service(
        self,
        mock_semester_repo: MagicMock,
        mock_calendar_config_repo: MagicMock,
        mock_effective_schedule_service: MagicMock,
        mock_writer: MagicMock,
    ) -> CalendarCoachingService:
        return CalendarCoachingService(
            semester_repository=mock_semester_repo,
            calendar_config_repository=mock_calendar_config_repo,
            effective_schedule_service=mock_effective_schedule_service,
            calendar_writer=mock_writer,
        )

    @pytest.fixture
    def sample_brief(self) -> CoachingBrief:
        return CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
            topic_id="t1",
            topic_title="Síndrome cerebeloso",
        )

    def test_unauthorized_call_raises_error_and_blocks_write(
        self,
        coaching_service: CalendarCoachingService,
        mock_writer: MagicMock,
        sample_brief: CoachingBrief,
        guayaquil_tz: ZoneInfo,
    ) -> None:
        """Verify authorized=False raises CalendarWriteAuthorizationError and blocks write."""
        with pytest.raises(CalendarWriteAuthorizationError, match="require explicit authorization"):
            coaching_service.publish_class_brief(
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 8, 4),
                brief=sample_brief,
                time_min=datetime(2026, 8, 1, 0, 0, tzinfo=guayaquil_tz),
                time_max=datetime(2026, 8, 31, 23, 59, tzinfo=guayaquil_tz),
                authorized=False,  # Unauthorized!
            )
        mock_writer.publish.assert_not_called()

    def test_authorized_call_publishes_successfully(
        self,
        coaching_service: CalendarCoachingService,
        mock_writer: MagicMock,
        sample_brief: CoachingBrief,
        guayaquil_tz: ZoneInfo,
    ) -> None:
        """Verify authorized=True executes publish and returns result."""
        result = coaching_service.publish_class_brief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 4),
            brief=sample_brief,
            time_min=datetime(2026, 8, 1, 0, 0, tzinfo=guayaquil_tz),
            time_max=datetime(2026, 8, 31, 23, 59, tzinfo=guayaquil_tz),
            authorized=True,
        )

        assert result.action == CalendarPublishAction.CREATED
        assert result.event_id == "published_evt_1"
        mock_writer.publish.assert_called_once()

    def test_disabled_calendar_config_raises_error(
        self,
        coaching_service: CalendarCoachingService,
        mock_calendar_config_repo: MagicMock,
        mock_writer: MagicMock,
        sample_brief: CoachingBrief,
        guayaquil_tz: ZoneInfo,
    ) -> None:
        """Verify disabled calendar config raises CalendarConfigError."""
        mock_calendar_config_repo.get.return_value = CourseCalendarConfig(
            semester_id="2026-2",
            course_code="NEURO",
            enabled=False,
            calendar_id=None,
            aliases=["NEURO"],
        )

        with pytest.raises(CalendarConfigError, match="Calendar integration is disabled"):
            coaching_service.publish_class_brief(
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 8, 4),
                brief=sample_brief,
                time_min=datetime(2026, 8, 1, 0, 0, tzinfo=guayaquil_tz),
                time_max=datetime(2026, 8, 31, 23, 59, tzinfo=guayaquil_tz),
                authorized=True,
            )
        mock_writer.publish.assert_not_called()

    def test_cancelled_class_raises_error_and_blocks_write(
        self,
        coaching_service: CalendarCoachingService,
        mock_writer: MagicMock,
        guayaquil_tz: ZoneInfo,
    ) -> None:
        """Verify attempting to publish to a cancelled class raises CalendarPublishPlanError."""
        cancelled_brief = CoachingBrief(
            semester_id="2026-2",
            course_code="NEURO",
            class_date=date(2026, 8, 11),  # Cancelled in mock schedule!
            topic_title="Feriado",
        )

        with pytest.raises(
            CalendarPublishPlanError, match="Cannot publish coaching brief for cancelled class"
        ):
            coaching_service.publish_class_brief(
                semester_id="2026-2",
                course_code="NEURO",
                class_date=date(2026, 8, 11),
                brief=cancelled_brief,
                time_min=datetime(2026, 8, 1, 0, 0, tzinfo=guayaquil_tz),
                time_max=datetime(2026, 8, 31, 23, 59, tzinfo=guayaquil_tz),
                authorized=True,
            )
        mock_writer.publish.assert_not_called()
