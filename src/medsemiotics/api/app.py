"""FastAPI application serving the read-only MedSemiotics backend contracts.

Loop 0.8A gives the mobile and conversational surfaces something to consume: what is being taught
and what comes next. Loop 0.8B adds why something is not working — the coordination view — and when
the next classes are planned. Every endpoint is read-only, reads tracked configuration only, and
makes no external call: the backend holds no Google credential.

Loop 0.8D adds the class brief, which is always a draft: no publishing collaborator is wired into
the chain that builds it.

Loop 0.8C adds the one endpoint that does contact Google: the Calendar-reconciled effective
schedule, served only when a read-only Calendar credential is configured in the secret store. That
credential can read Calendar and nothing else; the backend still holds no Classroom credential and
still cannot write anywhere.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.openapi.utils import get_openapi

from medsemiotics.api.schemas import (
    BriefResponse,
    CoordinationResponse,
    CourseStateResponse,
    CourseSummary,
    EffectiveClassResponse,
    EffectiveScheduleResponse,
    HealthResponse,
    NextTopicResponse,
    PlannedClassResponse,
    ScheduleResponse,
    SemesterResponse,
    TeachingGuideResponse,
)
from medsemiotics.api.security import require_backend_token
from medsemiotics.api.settings import (
    BackendServices,
    BackendSettings,
    CalendarReaderFactory,
    build_backend_services,
    load_backend_settings,
)
from medsemiotics.domain.academic import SemesterConfig
from medsemiotics.domain.calendar import CourseCalendarConfig
from medsemiotics.domain.exceptions import (
    MedSemioticsError,
    TeachingCoachNoClassError,
)
from medsemiotics.domain.teaching_coach import TeachingCoachPreviewRequest
from medsemiotics.integrations.google_calendar.secret_backed_auth import (
    CALENDAR_CHANNEL_SECRETS,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Configure the application before it serves its first request.

    Access control reads the configured token before any endpoint body runs, so the wiring cannot
    be left to the first request that reaches an endpoint.
    """
    ensure_configured()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="MedSemiotics Teaching Copilot API",
    version="0.1.0",
    # The schema describes every contract this backend serves, so it is not public: it is served
    # at /openapi.json behind the same token as the data. The browser documentation pages are
    # disabled outright, because they fetch the schema without a bearer header and would only
    # ever render an error against a token-guarded backend.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def configure(
    settings: BackendSettings | None = None,
    *,
    calendar_reader_factory: CalendarReaderFactory | None = None,
) -> None:
    """Bind the application to a configuration root, access token, and Calendar reader.

    Args:
        settings: Settings to use; defaults to those the environment and secret store describe.
        calendar_reader_factory: Overrides how a Calendar reader is built.
    """
    resolved = settings if settings is not None else load_backend_settings()
    app.state.settings = resolved
    app.state.api_token = resolved.api_token
    app.state.services = build_backend_services(
        resolved,
        calendar_reader_factory=calendar_reader_factory,
    )
    app.state.configured = True


def ensure_configured() -> None:
    """Configure the application once, from the environment and secret store.

    Called from the lifespan hook, and again defensively wherever configuration is required, so a
    server that starts without running the lifespan still serves a configured application rather
    than reporting itself unconfigured.
    """
    if not getattr(app.state, "configured", False):
        configure()


def get_services() -> BackendServices:
    """Return the wired read-only services.

    Returns:
        The services every endpoint composes.
    """
    ensure_configured()
    return app.state.services  # type: ignore[no-any-return]


def _not_found(detail: str) -> HTTPException:
    """Build a 404 that never echoes a filesystem path."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@app.get(
    "/openapi.json",
    include_in_schema=False,
    dependencies=[Depends(require_backend_token)],
)
def read_openapi_schema() -> dict[str, Any]:
    """Return the API schema to an authenticated caller.

    A conversational surface fetches this once to learn the contracts it may call. It is guarded
    like the data itself: an unauthenticated caller learns nothing about the surface.

    Returns:
        The generated OpenAPI document.
    """
    return get_openapi(title=app.title, version=app.version, routes=app.routes)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Report that the service is running, without touching configuration."""
    return HealthResponse(
        status="ok",
        service="medsemiotics-teaching-copilot",
    )


@app.get(
    "/v1/semester",
    response_model=SemesterResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_semester() -> SemesterResponse:
    """Return the active semester and its active courses.

    Returns:
        The semester a mobile surface is currently working in.

    Raises:
        HTTPException: 404 when tracked configuration does not describe an active semester.
    """
    services = get_services()
    try:
        semester_id = services.current_semester_id()
        semester = services.semesters.get(semester_id)
    except MedSemioticsError as err:
        raise _not_found(
            f"No tracked semester configuration is available ({type(err).__name__})."
        ) from None

    return SemesterResponse(
        semester_id=semester.semester_id,
        display_name=semester.display_name,
        timezone=semester.timezone,
        courses=tuple(
            CourseSummary(code=course.code, name=course.name)
            for course in sorted(semester.courses, key=lambda course: course.code)
            if course.active
        ),
    )


@app.get(
    "/v1/courses/{course_code}/state",
    response_model=CourseStateResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_course_state(course_code: str) -> CourseStateResponse:
    """Return what has been taught in one course and what comes next.

    Args:
        course_code: Tracked course code, such as NEURO.

    Returns:
        Counts and per-topic progress derived from the syllabus and teaching log.

    Raises:
        HTTPException: 404 when the course has no tracked state in the active semester.
    """
    services = get_services()
    try:
        semester_id = services.current_semester_id()
        state = services.course_state.get_state(semester_id, course_code.upper())
    except MedSemioticsError as err:
        raise _not_found(
            f"No tracked academic state for '{course_code}' ({type(err).__name__})."
        ) from None

    return CourseStateResponse.from_state(state)


@app.get(
    "/v1/courses/{course_code}/next-topic",
    response_model=NextTopicResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_next_topic(course_code: str) -> NextTopicResponse:
    """Return the next required topic and the curated guidance for teaching it.

    This is the endpoint a phone opens before class: the next thing to teach, with the objectives,
    critical points, questions, pitfalls, and materials the catalog holds for it.

    Args:
        course_code: Tracked course code, such as NEURO.

    Returns:
        The next required topic, its curated guide when the catalog holds one, and a one-sentence
        explanation of the answer.

    Raises:
        HTTPException: 404 when the course has no tracked state in the active semester.
    """
    services = get_services()
    normalized = course_code.upper()
    try:
        semester_id = services.current_semester_id()
        state = services.course_state.get_state(semester_id, normalized)
    except MedSemioticsError as err:
        raise _not_found(
            f"No tracked academic state for '{course_code}' ({type(err).__name__})."
        ) from None

    next_topic = state.next_required_topic
    if next_topic is None:
        return NextTopicResponse(
            semester_id=state.semester_id,
            course_code=state.course_code,
            topic_id=None,
            guide=None,
            note="Every required topic in the tracked syllabus is already covered.",
        )

    try:
        guide = services.guides.get_guide(semester_id, normalized, next_topic.topic_id)
    except MedSemioticsError:
        return NextTopicResponse(
            semester_id=state.semester_id,
            course_code=state.course_code,
            topic_id=next_topic.topic_id,
            guide=None,
            note="The curated catalog holds no guide for this topic yet.",
        )

    return NextTopicResponse(
        semester_id=state.semester_id,
        course_code=state.course_code,
        topic_id=next_topic.topic_id,
        guide=TeachingGuideResponse.from_guide(guide),
        note=(f"Next required topic in planned order, currently {next_topic.status.value}."),
    )


@app.get(
    "/v1/courses/{course_code}/guides/{topic_id}",
    response_model=TeachingGuideResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_guide(course_code: str, topic_id: str) -> TeachingGuideResponse:
    """Return the curated guide for one topic.

    Args:
        course_code: Tracked course code, such as NEURO.
        topic_id: Tracked topic identifier.

    Returns:
        The curated guidance published for that topic.

    Raises:
        HTTPException: 404 when the catalog is disabled or holds no such guide.
    """
    services = get_services()
    try:
        semester_id = services.current_semester_id()
        guide = services.guides.get_guide(semester_id, course_code.upper(), topic_id)
    except MedSemioticsError as err:
        raise _not_found(
            f"No curated guide for '{topic_id}' in '{course_code}' ({type(err).__name__})."
        ) from None

    return TeachingGuideResponse.from_guide(guide)


@app.get(
    "/v1/coordination",
    response_model=CoordinationResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_coordination() -> CoordinationResponse:
    """Return whether each active course is wired for coordinated teaching support.

    The view reads tracked configuration only, so the Classroom binding of every course reports
    `not_read`: confirming it needs an authorized Classroom snapshot, which this backend cannot
    obtain because it holds no Google credential.

    Returns:
        Per-course Classroom and Calendar bindings, progress, readiness, and recorded gaps.

    Raises:
        HTTPException: 404 when tracked configuration does not describe an active semester.
    """
    services = get_services()
    try:
        semester_id = services.current_semester_id()
        semester = services.semesters.get(semester_id)
        calendar_configs = _load_calendar_configs(services, semester_id, semester)
        view = services.coordination.build_view(
            semester=semester,
            calendar_configs=calendar_configs,
            snapshot=None,
            requested_by="backend-read",
        )
    except MedSemioticsError as err:
        raise _not_found(
            f"The coordination view could not be built ({type(err).__name__})."
        ) from None

    return CoordinationResponse.from_view(
        view,
        note=(
            "Built from tracked configuration only. Classroom bindings report not_read because "
            "this backend holds no Google credential; Calendar bindings are the tracked "
            "configuration, not live events."
        ),
    )


@app.get(
    "/v1/courses/{course_code}/schedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_schedule(
    course_code: str,
    limit: int = Query(default=5, ge=1, le=50),
) -> ScheduleResponse:
    """Return the next planned class dates from the tracked baseline schedule.

    These are planned dates, not confirmed ones: cancellations, makeup sessions, and exact times
    are operational Calendar evidence this backend does not read.

    Args:
        course_code: Tracked course code, such as NEURO.
        limit: How many upcoming dates to return.

    Returns:
        The baseline schedule window and the next planned class dates within it.

    Raises:
        HTTPException: 404 when the course has no tracked schedule in the active semester.
    """
    services = get_services()
    try:
        semester_id = services.current_semester_id()
        schedule = services.schedules.get(semester_id, course_code.upper())
    except MedSemioticsError as err:
        raise _not_found(
            f"No tracked schedule for '{course_code}' ({type(err).__name__})."
        ) from None

    today = _today()
    upcoming = tuple(
        PlannedClassResponse(date=class_date, weekday=class_date.strftime("%A").lower())
        for class_date in schedule.all_class_dates
        if class_date >= today
    )[:limit]

    return ScheduleResponse(
        semester_id=schedule.semester_id,
        course_code=schedule.course_code,
        enabled=schedule.enabled,
        teaching_start_date=schedule.teaching_start_date,
        teaching_end_date=schedule.teaching_end_date,
        upcoming=upcoming,
        note=(
            "Planned baseline dates. Cancellations, makeup sessions, and exact meeting times are "
            "Calendar evidence this backend does not read."
        ),
    )


def _load_calendar_configs(
    services: BackendServices,
    semester_id: str,
    semester: SemesterConfig,
) -> list[CourseCalendarConfig]:
    """Load the tracked calendar binding of every active course, skipping those without one."""
    configs: list[CourseCalendarConfig] = []
    for course in semester.courses:
        if not course.active:
            continue
        try:
            configs.append(services.calendars.get(semester_id, course.code))
        except MedSemioticsError:
            continue
    return configs


def _today() -> date:
    """Return the current date, in UTC, for schedule windows."""
    return datetime.now(UTC).date()


@app.get(
    "/v1/courses/{course_code}/effective-schedule",
    response_model=EffectiveScheduleResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_effective_schedule(
    course_code: str,
    days: int = Query(default=14, ge=1, le=120),
) -> EffectiveScheduleResponse:
    """Return the tracked baseline reconciled with Calendar evidence.

    Unlike every other endpoint, this one reads Google Calendar — with a credential minted for
    `calendar.readonly` and nothing else. Cancellations, makeup sessions, and exact meeting times
    become visible here; an unobserved baseline date stays a scheduled class rather than
    disappearing.

    Args:
        course_code: Tracked course code, such as NEURO.
        days: How many days ahead to reconcile.

    Returns:
        The reconciled classes within the window.

    Raises:
        HTTPException: 503 when no Calendar credential is configured, 404 when the course has no
            tracked schedule in the active semester.
    """
    services = get_services()
    if services.calendar_reader_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This backend has no Calendar credential configured, so it cannot reconcile the "
                "baseline with Calendar evidence. Configure "
                f"{', '.join(CALENDAR_CHANNEL_SECRETS)} in the secret store, or read the planned "
                "baseline from /v1/courses/{course_code}/schedule."
            ),
        )

    try:
        semester_id = services.current_semester_id()
        semester = services.semesters.get(semester_id)
        timezone = ZoneInfo(semester.timezone)
    except (MedSemioticsError, ValueError) as err:
        raise _not_found(
            f"No tracked semester configuration is available ({type(err).__name__})."
        ) from None

    window_start = datetime.now(timezone)
    window_end = window_start + timedelta(days=days)

    try:
        schedule = services.effective_schedule_service(timezone).get_effective_schedule(
            semester_id=semester_id,
            course_code=course_code.upper(),
            time_min=window_start,
            time_max=window_end,
        )
    except MedSemioticsError as err:
        raise _not_found(
            f"No reconciled schedule for '{course_code}' ({type(err).__name__})."
        ) from None

    return EffectiveScheduleResponse(
        semester_id=schedule.semester_id,
        course_code=schedule.course_code,
        window_start=window_start,
        window_end=window_end,
        classes=tuple(
            EffectiveClassResponse(
                date=event.date,
                status=event.status,
                source=event.source,
                start=event.start,
                end=event.end,
                title=event.title,
                notes=event.notes,
            )
            for event in schedule.events
            if window_start.date() <= event.date <= window_end.date()
        ),
        note=(
            "Tracked baseline reconciled with Calendar evidence read through a credential scoped "
            "to calendar.readonly. An unobserved baseline date remains a scheduled class."
        ),
    )


@app.get(
    "/v1/courses/{course_code}/brief",
    response_model=BriefResponse,
    dependencies=[Depends(require_backend_token)],
)
def read_brief(
    course_code: str,
    class_date: Annotated[date | None, Query(alias="date")] = None,
) -> BriefResponse:
    """Return a reviewable class brief for one teaching day.

    The topic is selected automatically from the reconciled schedule and the tracked academic
    state, then composed with the curated guide. The result is always a **draft**: publishing it to
    Calendar or Classroom is a separate action that requires a named human approval, and no
    publishing collaborator exists in the chain that produced this response.

    Args:
        course_code: Tracked course code, such as NEURO.
        class_date: Teaching day to brief; defaults to today in the academic timezone.

    Returns:
        The draft brief, marked as one.

    Raises:
        HTTPException: 503 when no Calendar credential is configured, 404 when there is no class
            that day or the tracked state cannot produce a brief.
    """
    services = get_services()
    if services.calendar_reader_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This backend has no Calendar credential configured, so it cannot resolve which "
                "class to brief. Configure "
                f"{', '.join(CALENDAR_CHANNEL_SECRETS)} in the secret store."
            ),
        )

    try:
        semester_id = services.current_semester_id()
        semester = services.semesters.get(semester_id)
        timezone = ZoneInfo(semester.timezone)
    except (MedSemioticsError, ValueError) as err:
        raise _not_found(
            f"No tracked semester configuration is available ({type(err).__name__})."
        ) from None

    target_date = class_date if class_date is not None else datetime.now(timezone).date()
    window_start = datetime.combine(target_date, time.min, tzinfo=timezone)
    window_end = window_start + timedelta(days=1)

    try:
        preview = services.teaching_coach_preview_service(timezone).preview_class_brief(
            TeachingCoachPreviewRequest(
                semester_id=semester_id,
                course_code=course_code.upper(),
                class_date=target_date,
                time_min=window_start,
                time_max=window_end,
                requested_by="backend-read",
            )
        )
    except TeachingCoachNoClassError:
        raise _not_found(
            f"No effective class for '{course_code}' on {target_date.isoformat()}."
        ) from None
    except MedSemioticsError as err:
        raise _not_found(
            f"No brief could be composed for '{course_code}' on "
            f"{target_date.isoformat()} ({type(err).__name__})."
        ) from None

    return BriefResponse.from_preview(
        preview,
        note=(
            "A draft for review. Publishing it to Calendar or Classroom is a separate action that "
            "requires a named human approval; this endpoint cannot publish anything."
        ),
    )
