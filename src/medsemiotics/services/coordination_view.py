"""Compose the read-only coordination view across Classroom, Calendar, and academic state."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from medsemiotics.agents.framework import AgentCapabilityFramework
from medsemiotics.domain.academic import Course, SemesterConfig
from medsemiotics.domain.academic_state import CourseAcademicState
from medsemiotics.domain.agents import AgentActionIntent, AgentPillar, AutonomyLevel
from medsemiotics.domain.calendar import CourseCalendarConfig
from medsemiotics.domain.coordination_view import (
    AcademicProgressSummary,
    CalendarLink,
    CalendarLinkStatus,
    ClassroomLink,
    ClassroomLinkStatus,
    CoordinationReadiness,
    CoordinationView,
    CourseCoordinationEntry,
    UnmatchedExternalCourse,
)
from medsemiotics.domain.exceptions import CoordinationViewError
from medsemiotics.domain.external_courses import (
    ExternalCourse,
    ExternalCourseSnapshot,
    normalize_course_name,
)
from medsemiotics.services.course_state_service import CourseStateService

CAPABILITY_ID = "coordination.course-coordination-view"


@dataclass(frozen=True)
class _ClassroomMatches:
    """Classroom bindings for every requested course plus the courses nothing claimed."""

    links: dict[str, ClassroomLink]
    unmatched: tuple[UnmatchedExternalCourse, ...]


def _tokens(value: str) -> tuple[str, ...]:
    """Split a label into normalized comparison tokens."""
    return tuple(normalize_course_name(value).split())


def _contains_token_sequence(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    """Report whether a token sequence appears contiguously inside another.

    Whole-token comparison keeps 'neuro' from matching 'neurogastroenterologia'.

    Args:
        haystack: Tokens of the external course name.
        needle: Tokens of a tracked course label.

    Returns:
        True when the needle appears as a contiguous run of whole tokens.
    """
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[start : start + len(needle)] == needle
        for start in range(len(haystack) - len(needle) + 1)
    )


class CoordinationViewService:
    """Build one explainable coordination view without contacting any provider."""

    def __init__(
        self,
        capability_framework: AgentCapabilityFramework,
        course_state_service: CourseStateService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize with the capability registry and a read-only academic state source."""
        self._capability_framework = capability_framework
        self._course_state_service = course_state_service
        self._clock = clock or (lambda: datetime.now(UTC))

    def build_view(
        self,
        *,
        semester: SemesterConfig,
        calendar_configs: Sequence[CourseCalendarConfig],
        snapshot: ExternalCourseSnapshot | None,
        requested_by: str,
    ) -> CoordinationView:
        """Compose the coordination view for every active course in one semester.

        Args:
            semester: Tracked semester configuration.
            calendar_configs: Tracked course calendar bindings for the same semester.
            snapshot: Provider-neutral Classroom snapshot, or None when no read was authorized.
            requested_by: Accountable requester recorded in the view.

        Returns:
            Deterministic CoordinationView ordered by course code.

        Raises:
            AgentAuthorizationError: If the intent exceeds the Coordination OBSERVE boundary.
            CoordinationViewError: If any input describes another semester or course.
        """
        self._capability_framework.authorize(
            AgentActionIntent(
                agent=AgentPillar.COORDINATION,
                capability_id=CAPABILITY_ID,
                requested_autonomy=AutonomyLevel.OBSERVE,
                requested_by=requested_by,
                rationale=f"Compose the coordination view for {semester.semester_id}.",
            )
        )

        calendar_by_course = self._index_calendar_configs(semester, calendar_configs)
        active_courses = sorted(
            (course for course in semester.courses if course.active),
            key=lambda course: course.code,
        )
        matches = self._match_classroom_courses(active_courses, calendar_by_course, snapshot)

        entries = tuple(
            self._build_entry(
                course=course,
                semester_id=semester.semester_id,
                calendar_config=calendar_by_course.get(course.code),
                classroom=matches.links[course.code],
            )
            for course in active_courses
        )

        return CoordinationView(
            semester_id=semester.semester_id,
            generated_at=self._generated_at(),
            requested_by=requested_by,
            entries=entries,
            unmatched_external_courses=matches.unmatched,
            inactive_course_codes=tuple(
                sorted(course.code for course in semester.courses if not course.active)
            ),
        )

    @staticmethod
    def _index_calendar_configs(
        semester: SemesterConfig,
        calendar_configs: Sequence[CourseCalendarConfig],
    ) -> dict[str, CourseCalendarConfig]:
        """Index calendar bindings by course, rejecting configuration from another scope."""
        indexed: dict[str, CourseCalendarConfig] = {}
        for config in calendar_configs:
            if config.semester_id != semester.semester_id:
                msg = (
                    f"Calendar configuration for '{config.course_code}' belongs to semester "
                    f"'{config.semester_id}', not '{semester.semester_id}'."
                )
                raise CoordinationViewError(msg)
            if config.course_code in indexed:
                msg = f"Duplicate calendar configuration for course '{config.course_code}'."
                raise CoordinationViewError(msg)
            indexed[config.course_code] = config
        return indexed

    def _match_classroom_courses(
        self,
        courses: Sequence[Course],
        calendar_by_course: dict[str, CourseCalendarConfig],
        snapshot: ExternalCourseSnapshot | None,
    ) -> "_ClassroomMatches":
        """Bind tracked courses to external courses without ever guessing."""
        if snapshot is None:
            return _ClassroomMatches(
                links={
                    course.code: ClassroomLink(
                        status=ClassroomLinkStatus.NOT_READ,
                        reason="No authorized Classroom snapshot was supplied for this view.",
                    )
                    for course in courses
                },
                unmatched=(),
            )

        candidates: dict[str, tuple[ExternalCourse, ...]] = {
            course.code: tuple(
                external
                for external in snapshot.courses
                if self._is_candidate(external, course, calendar_by_course.get(course.code))
            )
            for course in courses
        }

        claim_counts: dict[str, int] = {}
        for course_candidates in candidates.values():
            if len(course_candidates) == 1:
                external_id = course_candidates[0].external_id
                claim_counts[external_id] = claim_counts.get(external_id, 0) + 1

        links: dict[str, ClassroomLink] = {}
        linked_ids: set[str] = set()
        for course in courses:
            course_candidates = candidates[course.code]
            if not course_candidates:
                links[course.code] = ClassroomLink(
                    status=ClassroomLinkStatus.NOT_FOUND,
                    reason=(
                        "No accessible Classroom course name contains the course code, name, or "
                        "a configured alias."
                    ),
                )
                continue

            if len(course_candidates) > 1:
                links[course.code] = ClassroomLink(
                    status=ClassroomLinkStatus.AMBIGUOUS,
                    candidate_ids=tuple(candidate.external_id for candidate in course_candidates),
                    reason=(
                        f"{len(course_candidates)} accessible Classroom courses match this "
                        "course; a human must disambiguate before it can be linked."
                    ),
                )
                continue

            candidate = course_candidates[0]
            if claim_counts.get(candidate.external_id, 0) > 1:
                links[course.code] = ClassroomLink(
                    status=ClassroomLinkStatus.AMBIGUOUS,
                    candidate_ids=(candidate.external_id,),
                    reason=(
                        "One accessible Classroom course matches more than one tracked course; "
                        "a human must disambiguate before it can be linked."
                    ),
                )
                continue

            linked_ids.add(candidate.external_id)
            links[course.code] = ClassroomLink(
                status=ClassroomLinkStatus.LINKED,
                external_id=candidate.external_id,
                display_name=candidate.display_name,
                lifecycle=candidate.lifecycle,
                reason="Exactly one accessible Classroom course matches this course.",
            )

        unmatched = tuple(
            UnmatchedExternalCourse(
                external_id=external.external_id,
                display_name=external.display_name,
                lifecycle=external.lifecycle,
            )
            for external in snapshot.courses
            if external.external_id not in linked_ids
        )
        return _ClassroomMatches(links=links, unmatched=unmatched)

    @staticmethod
    def _is_candidate(
        external: ExternalCourse,
        course: Course,
        calendar_config: CourseCalendarConfig | None,
    ) -> bool:
        """Report whether an external course name carries a label of the tracked course."""
        labels = [course.code, course.name]
        if calendar_config is not None:
            labels.extend(calendar_config.aliases)

        external_tokens = _tokens(external.display_name)
        return any(_contains_token_sequence(external_tokens, _tokens(label)) for label in labels)

    def _build_entry(
        self,
        *,
        course: Course,
        semester_id: str,
        calendar_config: CourseCalendarConfig | None,
        classroom: ClassroomLink,
    ) -> CourseCoordinationEntry:
        """Compose one course entry and record every coordination gap it has."""
        calendar = self._build_calendar_link(calendar_config)
        state = self._course_state_service.get_state(semester_id, course.code)
        self._validate_state_scope(state, semester_id=semester_id, course_code=course.code)
        academic = self._summarize_state(state)

        blockers: list[str] = []
        if classroom.status is not ClassroomLinkStatus.LINKED:
            blockers.append(f"classroom: {classroom.reason}")
        if calendar.status is not CalendarLinkStatus.CONFIGURED:
            blockers.append(f"calendar: {calendar.reason}")
        if academic.total_topics == 0:
            blockers.append("syllabus: no planned topics are tracked for this course.")

        if not blockers:
            readiness = CoordinationReadiness.READY
        elif academic.total_topics == 0:
            readiness = CoordinationReadiness.BLOCKED
        else:
            readiness = CoordinationReadiness.PARTIAL

        return CourseCoordinationEntry(
            course_code=course.code,
            course_name=course.name,
            classroom=classroom,
            calendar=calendar,
            academic=academic,
            readiness=readiness,
            blockers=tuple(blockers),
        )

    @staticmethod
    def _build_calendar_link(calendar_config: CourseCalendarConfig | None) -> CalendarLink:
        """Describe the tracked Calendar binding without contacting Google Calendar."""
        if calendar_config is None:
            return CalendarLink(
                status=CalendarLinkStatus.MISSING,
                reason="No calendar configuration is tracked for this course.",
            )
        if not calendar_config.enabled:
            return CalendarLink(
                status=CalendarLinkStatus.DISABLED,
                calendar_id=calendar_config.calendar_id,
                reason="The tracked calendar binding is disabled.",
            )
        return CalendarLink(
            status=CalendarLinkStatus.CONFIGURED,
            calendar_id=calendar_config.calendar_id,
            reason="A calendar is bound and enabled for this course.",
        )

    @staticmethod
    def _summarize_state(state: CourseAcademicState) -> AcademicProgressSummary:
        """Reduce projected academic state to counts and the next required topic."""
        next_topic = state.next_required_topic
        return AcademicProgressSummary(
            total_topics=len(state.topics),
            completed_topics=len(state.completed_topics),
            in_progress_topics=len(state.in_progress_topics),
            not_started_topics=len(state.not_started_topics),
            skipped_topics=len(state.skipped_topics),
            next_required_topic_id=next_topic.topic_id if next_topic is not None else None,
        )

    @staticmethod
    def _validate_state_scope(
        state: CourseAcademicState,
        *,
        semester_id: str,
        course_code: str,
    ) -> None:
        """Refuse academic state projected for another scope."""
        if state.semester_id != semester_id or state.course_code != course_code:
            msg = (
                f"Academic state for {state.course_code} ({state.semester_id}) does not match "
                f"the requested scope {course_code} ({semester_id})."
            )
            raise CoordinationViewError(msg)

    def _generated_at(self) -> datetime:
        """Obtain a timezone-aware generation timestamp."""
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
            msg = "Coordination view clock must return a timezone-aware timestamp"
            raise CoordinationViewError(msg)
        return timestamp
