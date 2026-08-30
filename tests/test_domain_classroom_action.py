"""Tests for the Loop 0.6E single Classroom action contracts."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from medsemiotics.domain.classroom_action import (
    ClassroomActionApproval,
    ClassroomActionDecision,
    ClassroomActionPlan,
    ClassroomActionRecord,
    ClassroomActionStatus,
    ClassroomActionType,
)

PREPARED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def make_plan(**updates: object) -> ClassroomActionPlan:
    """Build the only Classroom action this contract allows."""
    values: dict[str, object] = {
        "action_type": ClassroomActionType.CREATE_COURSEWORK_DRAFT,
        "semester_id": "2026-2",
        "course_code": "NEURO",
        "external_course_id": "770001",
        "topic_id": "neuro-02",
        "title": "Taller de exploración de pares craneales",
        "instructions": "Revisar el caso clínico antes de la sesión.",
        "due_date": date(2026, 9, 12),
        "prepared_by": "course-director",
        "prepared_at": PREPARED_AT,
    }
    values.update(updates)
    return ClassroomActionPlan(**values)  # type: ignore[arg-type]


def make_approval(**updates: object) -> ClassroomActionApproval:
    """Build a named approval bound to the plan content."""
    values: dict[str, object] = {
        "approved_by": "department-head",
        "approved_at": PREPARED_AT,
        "content_fingerprint": make_plan().content_fingerprint,
    }
    values.update(updates)
    return ClassroomActionApproval(**values)  # type: ignore[arg-type]


def make_record(**updates: object) -> ClassroomActionRecord:
    """Build one applied-action ledger entry."""
    values: dict[str, object] = {
        "identity_key": make_plan().identity_key,
        "external_course_id": "770001",
        "applied_at": PREPARED_AT,
        "applied_by": "course-director",
        "external_reference": "coursework-991",
    }
    values.update(updates)
    return ClassroomActionRecord(**values)  # type: ignore[arg-type]


class TestClassroomActionPlan:
    """Verify one plan describes exactly one non-grading write."""

    def test_normalizes_academic_identifiers(self) -> None:
        plan = make_plan(semester_id=" 2026-2 ", course_code=" neuro ", topic_id=" NEURO-02 ")

        assert plan.semester_id == "2026-2"
        assert plan.course_code == "NEURO"
        assert plan.topic_id == "neuro-02"

    def test_is_frozen_and_rejects_grading_fields(self) -> None:
        plan = make_plan()

        with pytest.raises(ValidationError):
            plan.title = "changed"  # type: ignore[misc]

        for prohibited in ("max_points", "grade", "assigned_students", "published"):
            with pytest.raises(ValidationError):
                make_plan(**{prohibited: 10})

    def test_requires_timezone_aware_preparation(self) -> None:
        with pytest.raises(ValidationError):
            make_plan(prepared_at=datetime(2026, 8, 30, 12, 30))

    def test_requires_accountable_and_identifiable_fields(self) -> None:
        with pytest.raises(ValidationError):
            make_plan(prepared_by="   ")

        with pytest.raises(ValidationError):
            make_plan(external_course_id="   ")

        with pytest.raises(ValidationError):
            make_plan(title="  ")

    def test_rejects_non_text_metadata(self) -> None:
        with pytest.raises(ValidationError):
            make_plan(prepared_by=2026)

        with pytest.raises(ValidationError):
            make_plan(instructions=2026)

    def test_rejects_a_title_without_comparable_characters(self) -> None:
        with pytest.raises(ValidationError):
            make_plan(title="́")

    def test_normalizes_optional_instructions(self) -> None:
        assert make_plan(instructions="   ").instructions is None
        assert make_plan(instructions=None).instructions is None


class TestPlanIdentityAndContent:
    """Verify idempotency identity and approval binding answer different questions."""

    def test_identity_ignores_reviewable_content(self) -> None:
        baseline = make_plan()
        edited = make_plan(
            instructions="Instrucciones corregidas.",
            due_date=date(2026, 9, 19),
        )

        assert baseline.identity_key == edited.identity_key
        assert baseline.content_fingerprint != edited.content_fingerprint

    def test_identity_ignores_title_case_and_accents(self) -> None:
        assert (
            make_plan(title="Taller de EXPLORACION de pares craneales").identity_key
            == make_plan().identity_key
        )

    @pytest.mark.parametrize(
        "changed",
        [
            {"course_code": "GASTRO"},
            {"external_course_id": "770002"},
            {"topic_id": "neuro-03"},
            {"title": "Otro taller"},
            {"semester_id": "2026-1"},
        ],
    )
    def test_identity_changes_with_the_work_it_describes(self, changed: dict[str, object]) -> None:
        assert make_plan(**changed).identity_key != make_plan().identity_key

    def test_identity_is_stable_across_preparation_metadata(self) -> None:
        later = make_plan(
            prepared_by="department-head",
            prepared_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        )

        assert later.identity_key == make_plan().identity_key
        assert later.content_fingerprint == make_plan().content_fingerprint


class TestApprovalAndRecord:
    """Verify approval and ledger evidence stay accountable."""

    def test_approval_requires_named_accountability(self) -> None:
        with pytest.raises(ValidationError):
            make_approval(approved_by="   ")

        with pytest.raises(ValidationError):
            make_approval(content_fingerprint="   ")

        with pytest.raises(ValidationError):
            make_approval(approved_at=datetime(2026, 8, 30, 12, 30))

    def test_record_requires_named_accountability(self) -> None:
        with pytest.raises(ValidationError):
            make_record(applied_by="   ")

        with pytest.raises(ValidationError):
            make_record(applied_at=datetime(2026, 8, 30, 12, 30))

        assert make_record(external_reference="  ").external_reference is None


class TestClassroomActionDecision:
    """Verify a decision never claims evidence it does not have."""

    def test_authorized_records_the_approver(self) -> None:
        with pytest.raises(ValidationError):
            ClassroomActionDecision(
                status=ClassroomActionStatus.AUTHORIZED,
                action_type=ClassroomActionType.CREATE_COURSEWORK_DRAFT,
                identity_key=make_plan().identity_key,
                reason="Authorized.",
            )

    @pytest.mark.parametrize(
        "status",
        [ClassroomActionStatus.DENIED, ClassroomActionStatus.ALREADY_APPLIED],
    )
    def test_unauthorized_statuses_never_record_an_approver(
        self,
        status: ClassroomActionStatus,
    ) -> None:
        with pytest.raises(ValidationError):
            ClassroomActionDecision(
                status=status,
                action_type=ClassroomActionType.CREATE_COURSEWORK_DRAFT,
                identity_key=make_plan().identity_key,
                approved_by="department-head",
                reason="Not authorized.",
            )

    def test_only_a_repeat_names_a_previously_applied_action(self) -> None:
        with pytest.raises(ValidationError):
            ClassroomActionDecision(
                status=ClassroomActionStatus.DENIED,
                action_type=ClassroomActionType.CREATE_COURSEWORK_DRAFT,
                identity_key=make_plan().identity_key,
                existing_reference="coursework-991",
                reason="Denied.",
            )

    def test_requires_a_reason(self) -> None:
        with pytest.raises(ValidationError):
            ClassroomActionDecision(
                status=ClassroomActionStatus.ALREADY_APPLIED,
                action_type=ClassroomActionType.CREATE_COURSEWORK_DRAFT,
                identity_key=make_plan().identity_key,
                reason="   ",
            )
