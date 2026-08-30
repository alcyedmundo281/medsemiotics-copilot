"""Runtime configuration for the read-only MedSemiotics backend.

The backend serves the minimized contracts a mobile or conversational surface consumes. It reads
tracked configuration from disk and its own access token from the same secret store the Classroom
caller uses; it holds no Google credential and makes no external call.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from medsemiotics.integrations.google_classroom.owner_authorized_caller import (
    build_secret_source,
)
from medsemiotics.services.calendar_config_repository import CalendarConfigRepository
from medsemiotics.services.course_state_service import CourseStateService
from medsemiotics.services.semester_config import load_current_semester_id
from medsemiotics.services.semester_repository import SemesterRepository
from medsemiotics.services.syllabus_repository import SyllabusRepository
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository
from medsemiotics.services.teaching_log_repository import TeachingLogRepository

CONFIG_ROOT_ENV_VAR = "MEDSEMIOTICS_CONFIG_ROOT"
API_TOKEN_SECRET = "MEDSEMIOTICS_API_TOKEN"

DEFAULT_CONFIG_ROOT = "config"


@dataclass(frozen=True)
class BackendSettings:
    """Where tracked configuration lives, and the token that guards the read endpoints."""

    config_root: Path
    api_token: str | None

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
    token = build_secret_source(source).read(API_TOKEN_SECRET)
    return BackendSettings(config_root=Path(configured_root), api_token=token)


@dataclass(frozen=True)
class BackendServices:
    """Read-only services the endpoints compose, all backed by tracked configuration."""

    settings: BackendSettings
    semesters: SemesterRepository
    course_state: CourseStateService
    guides: TeachingGuideRepository
    calendars: CalendarConfigRepository

    def current_semester_id(self) -> str:
        """Resolve the active semester from tracked configuration."""
        return load_current_semester_id(self.settings.current_semester_pointer)


def build_backend_services(settings: BackendSettings) -> BackendServices:
    """Wire the read-only services from one configuration root.

    Args:
        settings: Resolved backend settings.

    Returns:
        The services every read endpoint composes.
    """
    root = settings.config_root
    return BackendServices(
        settings=settings,
        semesters=SemesterRepository(root / "semesters"),
        course_state=CourseStateService(
            SyllabusRepository(root / "syllabi"),
            TeachingLogRepository(root / "teaching_logs"),
        ),
        guides=TeachingGuideRepository(root / "teaching_guides"),
        calendars=CalendarConfigRepository(root / "calendar"),
    )
