"""Unit tests for academic state projection and unplanned topic discovery."""

from datetime import date

import pytest

from medsemiotics.domain.academic_state import TopicProgressStatus
from medsemiotics.domain.exceptions import AcademicStateError
from medsemiotics.domain.syllabus import SyllabusPlan, SyllabusTopic
from medsemiotics.domain.teaching_log import (
    CoverageStatus,
    TeachingSession,
    TeachingSessionTopic,
)
from medsemiotics.services.academic_state import (
    build_course_academic_state,
    find_unplanned_taught_topic_ids,
)


class TestAcademicStateProjection:
    """Test suite for build_course_academic_state event processing rules."""

    @pytest.fixture
    def neuro_syllabus(self) -> SyllabusPlan:
        """Sample 3-topic NEURO syllabus."""
        return SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="neuro-intro", planned_order=1, required=True),
                SyllabusTopic(topic_id="mental-status", planned_order=2, required=True),
                SyllabusTopic(topic_id="cranial-nerves", planned_order=3, required=True),
            ],
        )

    def test_no_teaching_sessions_all_not_started(self, neuro_syllabus: SyllabusPlan) -> None:
        """Verify empty session history yields all topics as not_started."""
        state = build_course_academic_state(neuro_syllabus, [])
        assert len(state.topics) == 3
        assert all(t.status == TopicProgressStatus.NOT_STARTED for t in state.topics)
        assert all(t.session_count == 0 for t in state.topics)
        assert all(t.first_taught_date is None for t in state.topics)
        assert state.completion_ratio == 0.0

    @pytest.mark.parametrize(
        ("event_status", "expected_topic_status"),
        [
            (CoverageStatus.INTRODUCED, TopicProgressStatus.IN_PROGRESS),
            (CoverageStatus.PARTIAL, TopicProgressStatus.IN_PROGRESS),
            (CoverageStatus.COMPLETED, TopicProgressStatus.COMPLETED),
            (CoverageStatus.SKIPPED, TopicProgressStatus.SKIPPED),
            (CoverageStatus.REVIEWED, TopicProgressStatus.IN_PROGRESS),
        ],
    )
    def test_single_session_events(
        self,
        neuro_syllabus: SyllabusPlan,
        event_status: CoverageStatus,
        expected_topic_status: TopicProgressStatus,
    ) -> None:
        """Verify each CoverageStatus transitions an initial not_started topic correctly."""
        session = TeachingSession(
            session_id="session-01",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="neuro-intro", status=event_status)],
        )

        state = build_course_academic_state(neuro_syllabus, [session])
        intro_prog = next(t for t in state.topics if t.topic_id == "neuro-intro")
        assert intro_prog.status == expected_topic_status
        assert intro_prog.session_count == 1
        assert intro_prog.first_taught_date == date(2026, 8, 15)
        assert intro_prog.last_taught_date == date(2026, 8, 15)

    def test_completed_is_terminal(self, neuro_syllabus: SyllabusPlan) -> None:
        """Verify once completed, subsequent events (partial, introduced, reviewed, skipped) cannot regress status."""
        sessions = [
            TeachingSession(
                session_id="session-01",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED)],
            ),
            TeachingSession(
                session_id="session-02",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 18),
                sequence_number=2,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.PARTIAL)],
            ),
            TeachingSession(
                session_id="session-03",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 20),
                sequence_number=3,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.REVIEWED)],
            ),
            TeachingSession(
                session_id="session-04",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 22),
                sequence_number=4,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.SKIPPED)],
            ),
        ]

        state = build_course_academic_state(neuro_syllabus, sessions)
        intro_prog = next(t for t in state.topics if t.topic_id == "neuro-intro")
        assert intro_prog.status == TopicProgressStatus.COMPLETED
        assert intro_prog.session_count == 4
        assert intro_prog.first_taught_date == date(2026, 8, 15)
        assert intro_prog.last_taught_date == date(2026, 8, 22)

    def test_skipped_transitions(self, neuro_syllabus: SyllabusPlan) -> None:
        """Verify transitions starting from skipped status."""
        # skipped -> introduced => in_progress
        sessions_intro = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.SKIPPED)],
            ),
            TeachingSession(
                session_id="s2",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 18),
                sequence_number=2,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.INTRODUCED)],
            ),
        ]
        state_intro = build_course_academic_state(neuro_syllabus, sessions_intro)
        assert state_intro.topics[0].status == TopicProgressStatus.IN_PROGRESS

        # skipped -> completed => completed
        sessions_comp = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.SKIPPED)],
            ),
            TeachingSession(
                session_id="s2",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 18),
                sequence_number=2,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED)],
            ),
        ]
        state_comp = build_course_academic_state(neuro_syllabus, sessions_comp)
        assert state_comp.topics[0].status == TopicProgressStatus.COMPLETED

        # skipped -> reviewed => remains skipped
        sessions_rev = [
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.SKIPPED)],
            ),
            TeachingSession(
                session_id="s2",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 18),
                sequence_number=2,
                topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.REVIEWED)],
            ),
        ]
        state_rev = build_course_academic_state(neuro_syllabus, sessions_rev)
        assert state_rev.topics[0].status == TopicProgressStatus.SKIPPED

    def test_chronological_ordering_regardless_of_input_order(
        self, neuro_syllabus: SyllabusPlan
    ) -> None:
        """Verify projector sorts sessions chronologically before processing."""
        # Out-of-order input: session 2 (partial) passed before session 1 (completed)
        session_early = TeachingSession(
            session_id="s1",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 10),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.PARTIAL)],
        )
        session_late = TeachingSession(
            session_id="s2",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=2,
            topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED)],
        )

        state = build_course_academic_state(neuro_syllabus, [session_late, session_early])
        intro = state.topics[0]
        assert intro.status == TopicProgressStatus.COMPLETED
        assert intro.first_taught_date == date(2026, 8, 10)
        assert intro.last_taught_date == date(2026, 8, 15)
        assert intro.session_count == 2


class TestScopeValidation:
    """Test suite for semester and course scope enforcement."""

    @pytest.fixture
    def sample_syllabus(self) -> SyllabusPlan:
        return SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[SyllabusTopic(topic_id="neuro-intro", planned_order=1)],
        )

    def test_projector_rejects_wrong_semester(self, sample_syllabus: SyllabusPlan) -> None:
        session = TeachingSession(
            session_id="s1",
            semester_id="2026-1",  # Wrong semester
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED)],
        )
        with pytest.raises(AcademicStateError, match="expected semester '2026-2'"):
            build_course_academic_state(sample_syllabus, [session])

    def test_projector_rejects_wrong_course(self, sample_syllabus: SyllabusPlan) -> None:
        session = TeachingSession(
            session_id="s1",
            semester_id="2026-2",
            course_code="GASTRO",  # Wrong course
            session_date=date(2026, 8, 15),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED)],
        )
        with pytest.raises(AcademicStateError, match="expected course 'NEURO'"):
            build_course_academic_state(sample_syllabus, [session])

    def test_unplanned_finder_rejects_wrong_scope(self, sample_syllabus: SyllabusPlan) -> None:
        session = TeachingSession(
            session_id="s1",
            semester_id="2026-1",
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="unplanned-topic", status=CoverageStatus.COMPLETED)],
        )
        with pytest.raises(AcademicStateError):
            find_unplanned_taught_topic_ids(sample_syllabus, [session])


class TestUnplannedTopicsDiscovery:
    """Test suite for find_unplanned_taught_topic_ids."""

    @pytest.fixture
    def syllabus(self) -> SyllabusPlan:
        return SyllabusPlan(
            semester_id="2026-2",
            course_code="NEURO",
            topics=[
                SyllabusTopic(topic_id="neuro-intro", planned_order=1),
                SyllabusTopic(topic_id="mental-status", planned_order=2),
            ],
        )

    def test_no_unplanned_topics(self, syllabus: SyllabusPlan) -> None:
        """Verify empty list when all taught topics are in the syllabus."""
        session = TeachingSession(
            session_id="s1",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED)],
        )
        unplanned = find_unplanned_taught_topic_ids(syllabus, [session])
        assert unplanned == []

    def test_unplanned_topics_deterministic_and_deduplicated(
        self, syllabus: SyllabusPlan
    ) -> None:
        """Verify unplanned topics are deduplicated and ordered by first appearance."""
        sessions = [
            TeachingSession(
                session_id="s2",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 20),
                sequence_number=2,
                topics=[
                    TeachingSessionTopic(topic_id="movement-disorders", status=CoverageStatus.INTRODUCED),
                    TeachingSessionTopic(topic_id="neuro-emergency", status=CoverageStatus.PARTIAL),
                ],
            ),
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[
                    TeachingSessionTopic(topic_id="clinical-vignette-special", status=CoverageStatus.COMPLETED),
                    TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED),
                ],
            ),
            TeachingSession(
                session_id="s3",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 25),
                sequence_number=3,
                topics=[
                    # Duplicate appearance of clinical-vignette-special
                    TeachingSessionTopic(topic_id="clinical-vignette-special", status=CoverageStatus.REVIEWED),
                ],
            ),
        ]

        unplanned = find_unplanned_taught_topic_ids(syllabus, sessions)
        # Chronological appearance: s1 (Aug 15: clinical-vignette-special), then s2 (Aug 20: movement-disorders, neuro-emergency)
        assert unplanned == [
            "clinical-vignette-special",
            "movement-disorders",
            "neuro-emergency",
        ]
