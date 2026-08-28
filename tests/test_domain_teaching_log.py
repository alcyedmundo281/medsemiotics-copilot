"""Unit tests for Teaching Log domain models."""

from datetime import date

import pytest
from pydantic import ValidationError

from medsemiotics.domain.teaching_log import (
    CoverageStatus,
    TeachingSession,
    TeachingSessionTopic,
)


class TestTeachingLogDomainModel:
    """Test suite for TeachingSession and TeachingSessionTopic validation."""

    def test_valid_session(self) -> None:
        """Verify creating a valid TeachingSession with topics."""
        session = TeachingSession(
            session_id="session-01",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=1,
            notes="Introductory lecture on clinical semiology.",
            topics=[
                TeachingSessionTopic(
                    topic_id="neuro-intro",
                    status=CoverageStatus.COMPLETED,
                    notes="Covered anamnesis and baseline exam.",
                ),
                TeachingSessionTopic(
                    topic_id="mental-status",
                    status=CoverageStatus.PARTIAL,
                    notes="Covered alertness and orientation; memory deferred.",
                ),
            ],
        )

        assert session.session_id == "session-01"
        assert session.sequence_number == 1
        assert len(session.topics) == 2
        assert session.topics[0].status == CoverageStatus.COMPLETED
        assert session.topics[1].status == CoverageStatus.PARTIAL

    @pytest.mark.parametrize(
        "status",
        [
            CoverageStatus.INTRODUCED,
            CoverageStatus.PARTIAL,
            CoverageStatus.COMPLETED,
            CoverageStatus.REVIEWED,
            CoverageStatus.SKIPPED,
        ],
    )
    def test_all_coverage_statuses_valid(self, status: CoverageStatus) -> None:
        """Verify all enum values of CoverageStatus are accepted."""
        item = TeachingSessionTopic(topic_id="neuro-intro", status=status)
        assert item.status == status

    @pytest.mark.parametrize("invalid_seq", [0, -1, -10])
    def test_invalid_sequence_number(self, invalid_seq: int) -> None:
        """Verify sequence_number must be >= 1."""
        with pytest.raises(ValidationError):
            TeachingSession(
                session_id="session-01",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=invalid_seq,
                topics=[
                    TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.COMPLETED)
                ],
            )

    def test_duplicate_topic_in_same_session_rejected(self) -> None:
        """Verify duplicate topic IDs within a single session are rejected."""
        with pytest.raises(ValidationError, match="Duplicate topic IDs in teaching session"):
            TeachingSession(
                session_id="session-01",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[
                    TeachingSessionTopic(topic_id="neuro-intro", status=CoverageStatus.INTRODUCED),
                    TeachingSessionTopic(topic_id="NEURO-INTRO", status=CoverageStatus.COMPLETED),
                ],
            )

    def test_empty_topics_rejected(self) -> None:
        """Verify TeachingSession must contain at least one topic."""
        with pytest.raises(ValidationError, match="must contain at least one topic"):
            TeachingSession(
                session_id="session-01",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[],
            )

    def test_same_topic_in_separate_sessions_is_legal(self) -> None:
        """Verify a topic may appear across multiple distinct teaching sessions."""
        session1 = TeachingSession(
            session_id="session-01",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=1,
            topics=[TeachingSessionTopic(topic_id="cranial-nerves", status=CoverageStatus.PARTIAL)],
        )

        session2 = TeachingSession(
            session_id="session-02",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 18),
            sequence_number=2,
            topics=[
                TeachingSessionTopic(topic_id="cranial-nerves", status=CoverageStatus.COMPLETED)
            ],
        )

        assert session1.topics[0].topic_id == session2.topics[0].topic_id == "cranial-nerves"
        assert session1.topics[0].status == CoverageStatus.PARTIAL
        assert session2.topics[0].status == CoverageStatus.COMPLETED

    @pytest.mark.parametrize(
        ("raw_notes", "expected"),
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("  Exam conducted  ", "Exam conducted"),
        ],
    )
    def test_blank_notes_become_none(self, raw_notes: str | None, expected: str | None) -> None:
        """Verify blank notes on session and topic normalize to None."""
        session = TeachingSession(
            session_id="session-01",
            semester_id="2026-2",
            course_code="NEURO",
            session_date=date(2026, 8, 15),
            sequence_number=1,
            notes=raw_notes,
            topics=[
                TeachingSessionTopic(
                    topic_id="neuro-intro",
                    status=CoverageStatus.COMPLETED,
                    notes=raw_notes,
                )
            ],
        )
        assert session.notes == expected
        assert session.topics[0].notes == expected

    @pytest.mark.parametrize("invalid_val", [123, ["list"], {"k": "v"}])
    def test_teaching_log_non_string_types(self, invalid_val: object) -> None:
        """Verify non-string types on session_id and notes raise ValidationError."""
        with pytest.raises(ValidationError):
            TeachingSession(
                session_id=invalid_val,  # type: ignore[arg-type]
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                topics=[TeachingSessionTopic(topic_id="t1", status=CoverageStatus.COMPLETED)],
            )
        with pytest.raises(ValidationError):
            TeachingSession(
                session_id="s1",
                semester_id="2026-2",
                course_code="NEURO",
                session_date=date(2026, 8, 15),
                sequence_number=1,
                notes=invalid_val,  # type: ignore[arg-type]
                topics=[TeachingSessionTopic(topic_id="t1", status=CoverageStatus.COMPLETED)],
            )
        with pytest.raises(ValidationError):
            TeachingSessionTopic(
                topic_id="t1",
                status=CoverageStatus.COMPLETED,
                notes=invalid_val,  # type: ignore[arg-type]
            )
