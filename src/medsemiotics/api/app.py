"""FastAPI application serving the read-only MedSemiotics backend contracts.

Loop 0.8A gives the mobile and conversational surfaces something to consume: what is being taught
and what comes next. Loop 0.8B adds why something is not working — the coordination view — and when
the next classes are planned. Every endpoint is read-only, reads tracked configuration only, and
makes no external call: the backend holds no Google credential.

Because nothing here contacts Google, two things are deliberately absent: the Calendar-reconciled
effective schedule, and the full Teaching Coach brief that depends on it. Both need live Calendar
evidence and belong to an increment that runs with those credentials.
"""

from datetime import UTC, date, datetime

from fastapi import Depends, FastAPI, HTTPException, Query, status

from medsemiotics.api.schemas import (
    CoordinationResponse,
    CourseStateResponse,
    CourseSummary,
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
    build_backend_services,
    load_backend_settings,
)
from medsemiotics.domain.academic import SemesterConfig
from medsemiotics.domain.calendar import CourseCalendarConfig
from medsemiotics.domain.exceptions import MedSemioticsError

app = FastAPI(
    title="MedSemiotics Teaching Copilot API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


def configure(settings: BackendSettings | None = None) -> None:
    """Bind the application to a configuration root and access token.

    Args:
        settings: Settings to use; defaults to those the environment and secret store describe.
    """
    resolved = settings if settings is not None else load_backend_settings()
    app.state.settings = resolved
    app.state.api_token = resolved.api_token
    app.state.services = build_backend_services(resolved)


def get_services() -> BackendServices:
    """Return the wired read-only services.

    Returns:
        The services every endpoint composes.
    """
    services = getattr(app.state, "services", None)
    if services is None:
        configure()
        services = app.state.services
    return services  # type: ignore[no-any-return]


def _not_found(detail: str) -> HTTPException:
    """Build a 404 that never echoes a filesystem path."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


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
