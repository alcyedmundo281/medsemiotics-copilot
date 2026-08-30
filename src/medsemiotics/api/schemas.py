"""Response contracts for the read-only MedSemiotics backend.

Every model here is deliberately free of student data: courses, counts, topic identifiers, and
curated teaching content only.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from medsemiotics.domain.academic_state import CourseAcademicState, TopicProgressStatus
from medsemiotics.domain.teaching_coach import TeachingTopicGuide


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
