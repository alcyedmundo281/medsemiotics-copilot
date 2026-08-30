"""Response contracts for the read-only MedSemiotics backend.

Every model here is deliberately free of student data: courses, counts, topic identifiers, and
curated teaching content only.
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from medsemiotics.domain.academic_state import CourseAcademicState, TopicProgressStatus
from medsemiotics.domain.coordination_view import (
    CalendarLinkStatus,
    ClassroomLinkStatus,
    CoordinationReadiness,
    CoordinationView,
)
from medsemiotics.domain.effective_schedule import (
    EffectiveClassSource,
    EffectiveClassStatus,
)
from medsemiotics.domain.teaching_coach import (
    TeachingCoachPreviewResult,
    TeachingTopicGuide,
)


class HealthResponse(BaseModel):
    """Health check response payload schema."""

    status: str
    service: str


class CourseSummary(BaseModel):
    """One active course in the current semester."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, Field(description="Tracked course code")]
    name: Annotated[str, Field(description="Course title")]


class SemesterResponse(BaseModel):
    """The semester a mobile surface is currently working in."""

    model_config = ConfigDict(frozen=True)

    semester_id: str
    display_name: str
    timezone: str
    courses: tuple[CourseSummary, ...]


class TopicProgressResponse(BaseModel):
    """Progress of one planned topic, without any student-level detail."""

    model_config = ConfigDict(frozen=True)

    topic_id: str
    planned_order: int
    required: bool
    status: TopicProgressStatus
    session_count: int


class CourseStateResponse(BaseModel):
    """What has been taught and what comes next, derived from tracked state."""

    model_config = ConfigDict(frozen=True)

    semester_id: str
    course_code: str
    total_topics: int
    completed_topics: int
    in_progress_topics: int
    not_started_topics: int
    skipped_topics: int
    next_required_topic_id: str | None
    topics: tuple[TopicProgressResponse, ...]

    @classmethod
    def from_state(cls, state: CourseAcademicState) -> "CourseStateResponse":
        """Project an academic state onto the response contract.

        Args:
            state: Projected course academic state.

        Returns:
            The response a mobile surface receives.
        """
        next_topic = state.next_required_topic
        return cls(
            semester_id=state.semester_id,
            course_code=state.course_code,
            total_topics=len(state.topics),
            completed_topics=len(state.completed_topics),
            in_progress_topics=len(state.in_progress_topics),
            not_started_topics=len(state.not_started_topics),
            skipped_topics=len(state.skipped_topics),
            next_required_topic_id=next_topic.topic_id if next_topic is not None else None,
            topics=tuple(
                TopicProgressResponse(
                    topic_id=topic.topic_id,
                    planned_order=topic.planned_order,
                    required=topic.required,
                    status=topic.status,
                    session_count=topic.session_count,
                )
                for topic in state.ordered_topics
            ),
        )


class TeachingGuideResponse(BaseModel):
    """Curated guidance for one topic, as published in the tracked catalog."""

    model_config = ConfigDict(frozen=True)

    topic_id: str
    topic_title: str
    learning_objectives: tuple[str, ...]
    critical_points: tuple[str, ...]
    teaching_questions: tuple[str, ...]
    common_pitfalls: tuple[str, ...]
    material_notes: tuple[str, ...]

    @classmethod
    def from_guide(cls, guide: TeachingTopicGuide) -> "TeachingGuideResponse":
        """Project a curated guide onto the response contract.

        Args:
            guide: Curated teaching guide from the tracked catalog.

        Returns:
            The response a mobile surface receives.
        """
        return cls(
            topic_id=guide.topic_id,
            topic_title=guide.topic_title,
            learning_objectives=tuple(guide.learning_objectives),
            critical_points=tuple(guide.critical_points),
            teaching_questions=tuple(guide.teaching_questions),
            common_pitfalls=tuple(guide.common_pitfalls),
            material_notes=tuple(guide.material_notes),
        )


class NextTopicResponse(BaseModel):
    """The next required topic and the curated guidance for teaching it."""

    model_config = ConfigDict(frozen=True)

    semester_id: str
    course_code: str
    topic_id: str | None
    guide: TeachingGuideResponse | None
    note: Annotated[str, Field(description="Why this is the answer, in one sentence")]


class ClassroomLinkResponse(BaseModel):
    """How one course is bound to an external Classroom course."""

    model_config = ConfigDict(frozen=True)

    status: ClassroomLinkStatus
    external_id: str | None = None
    display_name: str | None = None
    candidate_ids: tuple[str, ...] = ()
    reason: str


class CalendarLinkResponse(BaseModel):
    """How one course is bound to a Google Calendar."""

    model_config = ConfigDict(frozen=True)

    status: CalendarLinkStatus
    calendar_id: str | None = None
    reason: str


class CourseCoordinationResponse(BaseModel):
    """Whether one course is wired for coordinated teaching support."""

    model_config = ConfigDict(frozen=True)

    course_code: str
    course_name: str
    classroom: ClassroomLinkResponse
    calendar: CalendarLinkResponse
    total_topics: int
    completed_topics: int
    next_required_topic_id: str | None
    readiness: CoordinationReadiness
    blockers: tuple[str, ...]


class CoordinationResponse(BaseModel):
    """The coordination view a teacher checks when something is not working."""

    model_config = ConfigDict(frozen=True)

    semester_id: str
    generated_at: datetime
    courses: tuple[CourseCoordinationResponse, ...]
    inactive_course_codes: tuple[str, ...]
    note: Annotated[str, Field(description="What this view did and did not consult")]

    @classmethod
    def from_view(cls, view: CoordinationView, note: str) -> "CoordinationResponse":
        """Project a coordination view onto the response contract.

        Args:
            view: Coordination view built from tracked configuration.
            note: One sentence describing the sources the view consulted.

        Returns:
            The response a mobile surface receives.
        """
        return cls(
            semester_id=view.semester_id,
            generated_at=view.generated_at,
            courses=tuple(
                CourseCoordinationResponse(
                    course_code=entry.course_code,
                    course_name=entry.course_name,
                    classroom=ClassroomLinkResponse(
                        status=entry.classroom.status,
                        external_id=entry.classroom.external_id,
                        display_name=entry.classroom.display_name,
                        candidate_ids=entry.classroom.candidate_ids,
                        reason=entry.classroom.reason,
                    ),
                    calendar=CalendarLinkResponse(
                        status=entry.calendar.status,
                        calendar_id=entry.calendar.calendar_id,
                        reason=entry.calendar.reason,
                    ),
                    total_topics=entry.academic.total_topics,
                    completed_topics=entry.academic.completed_topics,
                    next_required_topic_id=entry.academic.next_required_topic_id,
                    readiness=entry.readiness,
                    blockers=entry.blockers,
                )
                for entry in view.entries
            ),
            inactive_course_codes=view.inactive_course_codes,
            note=note,
        )


class PlannedClassResponse(BaseModel):
    """One planned class date from the tracked baseline schedule."""

    model_config = ConfigDict(frozen=True)

    date: date
    weekday: str


class ScheduleResponse(BaseModel):
    """Upcoming planned classes, before any Calendar evidence is applied."""

    model_config = ConfigDict(frozen=True)

    semester_id: str
    course_code: str
    enabled: bool
    teaching_start_date: date
    teaching_end_date: date
    upcoming: tuple[PlannedClassResponse, ...]
    note: Annotated[str, Field(description="Why these dates are planned, not confirmed")]


class EffectiveClassResponse(BaseModel):
    """One reconciled class meeting."""

    model_config = ConfigDict(frozen=True)

    date: date
    status: EffectiveClassStatus
    source: EffectiveClassSource
    start: datetime | None = None
    end: datetime | None = None
    title: str | None = None
    notes: str | None = None


class EffectiveScheduleResponse(BaseModel):
    """The tracked baseline reconciled with Calendar evidence."""

    model_config = ConfigDict(frozen=True)

    semester_id: str
    course_code: str
    window_start: datetime
    window_end: datetime
    classes: tuple[EffectiveClassResponse, ...]
    note: Annotated[str, Field(description="What evidence this reconciliation used")]


class BriefResponse(BaseModel):
    """A reviewable Teaching Coach draft, never a published one."""

    model_config = ConfigDict(frozen=True)

    semester_id: str
    course_code: str
    class_date: date
    topic_id: str | None
    topic_title: str
    learning_objectives: tuple[str, ...]
    coaching_tips: tuple[str, ...]
    teaching_questions: tuple[str, ...]
    common_pitfalls: tuple[str, ...]
    material_notes: tuple[str, ...]
    assignment_note: str | None = None
    preview_title: Annotated[str, Field(description="Title a reviewer would see")]
    preview_body: Annotated[str, Field(description="Rendered draft body a reviewer would read")]
    status: Annotated[str, Field(description="Always 'draft'")] = "draft"
    requires_approval: Annotated[
        bool, Field(description="Always true; publication is a separate approved action")
    ] = True
    note: Annotated[str, Field(description="What this draft is, and what it is not")]

    @classmethod
    def from_preview(cls, preview: TeachingCoachPreviewResult, note: str) -> "BriefResponse":
        """Project a preview result onto the response contract.

        Args:
            preview: Draft rendered by the Teaching Coach preview service.
            note: One sentence stating that this is a draft.

        Returns:
            The response a mobile surface receives.
        """
        brief = preview.draft.brief
        return cls(
            semester_id=brief.semester_id,
            course_code=brief.course_code,
            class_date=brief.class_date,
            topic_id=brief.topic_id,
            topic_title=brief.topic_title,
            learning_objectives=tuple(brief.learning_objectives),
            coaching_tips=tuple(brief.coaching_tips),
            teaching_questions=tuple(brief.teaching_questions),
            common_pitfalls=tuple(brief.common_pitfalls),
            material_notes=tuple(brief.material_notes),
            assignment_note=brief.assignment_note,
            preview_title=preview.preview_title,
            preview_body=preview.preview_body,
            note=note,
        )
