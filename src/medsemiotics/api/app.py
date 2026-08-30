"""FastAPI application serving the read-only MedSemiotics backend contracts.

Loop 0.8A gives the mobile and conversational surfaces something to consume: what is being taught,
what comes next, and how the courses are wired. Every endpoint is read-only, reads tracked
configuration only, and makes no external call — the backend holds no Google credential.
"""

from fastapi import Depends, FastAPI, HTTPException, status

from medsemiotics.api.schemas import (
    CourseStateResponse,
    CourseSummary,
    HealthResponse,
    NextTopicResponse,
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
