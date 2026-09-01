"""Runtime configuration for the read-only MedSemiotics backend.

The backend serves the minimized contracts a mobile or conversational surface consumes. It reads
tracked configuration from disk and its own access token from the same secret store the Classroom
caller uses; it holds no Google credential and makes no external call.
"""

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from medsemiotics.agents.framework import (
    AgentCapabilityFramework,
    build_default_agent_framework,
)
from medsemiotics.agents.teaching_coach import TeachingCoachAgent
from medsemiotics.integrations.google_calendar.client import GoogleCalendarReader
from medsemiotics.integrations.google_calendar.secret_backed_auth import (
    CalendarReadCredentials,
    build_calendar_credentials,
    load_calendar_read_credentials,
)
from medsemiotics.integrations.secrets import build_secret_source
from medsemiotics.services.calendar_config_repository import CalendarConfigRepository
from medsemiotics.services.coordination_view import CoordinationViewService
from medsemiotics.services.course_state_service import CourseStateService
from medsemiotics.services.curated_teaching_coach import CuratedTeachingCoachService
from medsemiotics.services.effective_schedule_service import EffectiveScheduleService
from medsemiotics.services.effective_teaching_day_service import EffectiveTeachingDayService
from medsemiotics.services.schedule_repository import ScheduleRepository
from medsemiotics.services.semester_config import load_current_semester_id
from medsemiotics.services.semester_repository import SemesterRepository
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_coach_preview import TeachingCoachPreviewService
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository
from medsemiotics.services.teaching_log_repository import TeachingLogRepository

CONFIG_ROOT_ENV_VAR = "MEDSEMIOTICS_CONFIG_ROOT"
API_TOKEN_SECRET = "MEDSEMIOTICS_API_TOKEN"

DEFAULT_CONFIG_ROOT = "config"


CalendarReaderFactory = Callable[[ZoneInfo], GoogleCalendarReader]


@dataclass(frozen=True)
class BackendSettings:
    """Where tracked configuration lives, and the credentials the backend is allowed to hold."""

    config_root: Path
    api_token: str | None
    calendar_credentials: CalendarReadCredentials | None = None

    @property
    def current_semester_pointer(self) -> Path:
        """Path to the tracked pointer naming the active semester."""
        return self.config_root / "current_semester.yaml"


def load_backend_settings(env: Mapping[str, str] | None = None) -> BackendSettings:
    """Read backend settings from the environment and secret store.

    Args:
        env: Environment mapping to read; defaults to the process environment.

    Returns:
        Settings describing the configuration root and the configured access token.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    configured_root = (source.get(CONFIG_ROOT_ENV_VAR) or "").strip() or DEFAULT_CONFIG_ROOT
    secrets = build_secret_source(source)
    raw_token = secrets.read(API_TOKEN_SECRET) or source.get(API_TOKEN_SECRET)
    api_token = raw_token.strip() if raw_token and raw_token.strip() else "local-dev-token"
    return BackendSettings(
        config_root=Path(configured_root),
        api_token=api_token,
        calendar_credentials=load_calendar_read_credentials(secrets),
    )


@dataclass(frozen=True)
class BackendServices:
    """Read-only services the endpoints compose, all backed by tracked configuration."""

    settings: BackendSettings
    semesters: SemesterRepository
    course_state: CourseStateService
    guides: TeachingGuideRepository
    calendars: CalendarConfigRepository
    schedules: ScheduleRepository
    capabilities: AgentCapabilityFramework
    coordination: CoordinationViewService
    syllabi: SyllabusRepository
    logs: TeachingLogRepository
    calendar_reader_factory: CalendarReaderFactory | None

    def effective_schedule_service(self, timezone: ZoneInfo) -> EffectiveScheduleService:
        """Build the reconciliation service, with a Calendar reader when one is configured.

        Args:
            timezone: Academic timezone used to interpret all-day boundaries.

        Returns:
            The service that reconciles the tracked baseline with Calendar evidence.
        """
        reader = self.calendar_reader_factory(timezone) if self.calendar_reader_factory else None
        return EffectiveScheduleService(
            semester_repository=self.semesters,
            schedule_repository=self.schedules,
            calendar_config_repository=self.calendars,
            calendar_reader=reader,
        )

    def teaching_coach_preview_service(self, timezone: ZoneInfo) -> TeachingCoachPreviewService:
        """Build the draft-only Teaching Coach preview chain.

        The chain reaches Calendar through the reconciliation service and stops at a draft: no
        publishing collaborator is wired into it at all.

        Args:
            timezone: Academic timezone used to interpret all-day boundaries.

        Returns:
            The service that selects the current topic and renders a reviewable draft.
        """
        teaching_day = EffectiveTeachingDayService(
            effective_schedule_service=self.effective_schedule_service(timezone),
            syllabus_repository=self.syllabi,
            teaching_log_repository=self.logs,
        )
        return TeachingCoachPreviewService(
            teaching_day_service=teaching_day,
            curated_teaching_coach_service=CuratedTeachingCoachService(
                teaching_guide_repository=self.guides,
                teaching_coach_agent=TeachingCoachAgent(
                    capability_framework=self.capabilities,
                    teaching_day_service=teaching_day,
                    course_state_service=self.course_state,
                ),
            ),
        )

    def current_semester_id(self) -> str:
        """Resolve the active semester from tracked configuration."""
        return load_current_semester_id(self.settings.current_semester_pointer)


def _default_calendar_reader_factory(
    credentials: CalendarReadCredentials,
) -> CalendarReaderFactory:
    """Build the factory that mints a read-only Calendar reader on demand."""

    def factory(timezone: ZoneInfo) -> GoogleCalendarReader:
        from googleapiclient.discovery import build

        service = build(
            "calendar",
            "v3",
            credentials=build_calendar_credentials(credentials),
            cache_discovery=False,
        )
        return GoogleCalendarReader(service, default_timezone=timezone)

    return factory


def build_backend_services(
    settings: BackendSettings,
    *,
    calendar_reader_factory: CalendarReaderFactory | None = None,
) -> BackendServices:
    """Wire the read-only services from one configuration root.

    Args:
        settings: Resolved backend settings.
        calendar_reader_factory: Overrides how a Calendar reader is built; defaults to the
            credential the secret store holds, and to no reader at all when it holds none.

    Returns:
        The services every read endpoint composes.
    """
    root = settings.config_root
    syllabi = SyllabusRepository(root / "syllabi")
    logs = TeachingLogRepository(root / "teaching_logs")
    course_state = CourseStateService(syllabi, logs)
    capabilities = build_default_agent_framework()
    return BackendServices(
        settings=settings,
        semesters=SemesterRepository(root / "semesters"),
        course_state=course_state,
        guides=TeachingGuideRepository(root / "teaching_guides"),
        calendars=CalendarConfigRepository(root / "calendar"),
        schedules=ScheduleRepository(root / "schedules"),
        syllabi=syllabi,
        logs=logs,
        capabilities=capabilities,
        coordination=CoordinationViewService(
            capability_framework=capabilities,
            course_state_service=course_state,
        ),
        calendar_reader_factory=(
            calendar_reader_factory
            if calendar_reader_factory is not None
            else (
                _default_calendar_reader_factory(settings.calendar_credentials)
                if settings.calendar_credentials is not None
                else None
            )
        ),
    )
