"""Tests for the private persistent Classroom applied-action ledger."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.domain.classroom_action import (
    ClassroomActionApproval,
    ClassroomActionPlan,
    ClassroomActionRecord,
    ClassroomActionStatus,
    ClassroomActionType,
)
from medsemiotics.domain.exceptions import (
    ClassroomActionLedgerPersistenceError,
    ClassroomActionLedgerValidationError,
)
from medsemiotics.services.classroom_action_ledger import ClassroomActionLedgerRepository
from medsemiotics.services.classroom_action_plan import ClassroomActionAuthorizer

NOW = datetime(2026, 8, 30, 4, 0, tzinfo=UTC)


def make_record(**updates: object) -> ClassroomActionRecord:
    """Build one valid private ledger record."""
    values: dict[str, object] = {
        "identity_key": "identity-1",
        "external_course_id": "course-123",
        "applied_at": NOW,
        "applied_by": "Alcy Torres",
        "external_reference": "coursework-456",
    }
    values.update(updates)
    return ClassroomActionRecord(**values)  # type: ignore[arg-type]


def make_plan() -> ClassroomActionPlan:
    """Build the exact action represented by the persistent record test."""
    return ClassroomActionPlan(
        action_type=ClassroomActionType.CREATE_COURSEWORK_DRAFT,
        semester_id="2026-2",
        course_code="NEURO",
        external_course_id="course-123",
        topic_id="neuro-intro-localizacion",
        title="Localización neurológica inicial",
        prepared_by="operator",
        prepared_at=NOW,
    )


class TestClassroomActionLedgerRepository:
    """Verify private ledger validation and atomic persistence."""

    def test_missing_ledger_is_empty(self, tmp_path: Path) -> None:
        repository = ClassroomActionLedgerRepository(tmp_path / "private" / "ledger.json")

        assert repository.load() == ()

    def test_appends_and_reloads_a_record(self, tmp_path: Path) -> None:
        path = tmp_path / "private" / "ledger.json"
        repository = ClassroomActionLedgerRepository(path)
        record = make_record()

        assert repository.append(record) == record
        assert ClassroomActionLedgerRepository(path).load() == (record,)
        assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1

    def test_exact_repeat_is_a_persistence_no_op(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.json"
        repository = ClassroomActionLedgerRepository(path)
        record = make_record()
        repository.append(record)
        original = path.read_bytes()

        assert repository.append(record) == record
        assert path.read_bytes() == original

    def test_conflicting_repeat_fails_closed(self, tmp_path: Path) -> None:
        repository = ClassroomActionLedgerRepository(tmp_path / "ledger.json")
        repository.append(make_record())

        with pytest.raises(ClassroomActionLedgerValidationError, match="different ledger"):
            repository.append(make_record(external_reference="different"))

    @pytest.mark.parametrize(
        "payload",
        [
            "not-json",
            "[]",
            '{"schema_version": 2, "records": []}',
            '{"schema_version": 1, "records": {}, "extra": true}',
            '{"schema_version": 1, "records": {}}',
            '{"schema_version": 1, "records": [{"identity_key": "only"}]}',
        ],
    )
    def test_malformed_ledgers_fail_closed(self, tmp_path: Path, payload: str) -> None:
        path = tmp_path / "ledger.json"
        path.write_text(payload, encoding="utf-8")

        with pytest.raises(ClassroomActionLedgerValidationError):
            ClassroomActionLedgerRepository(path).load()

    def test_duplicate_identities_fail_closed(self, tmp_path: Path) -> None:
        record = make_record().model_dump(mode="json")
        path = tmp_path / "ledger.json"
        path.write_text(
            json.dumps({"schema_version": 1, "records": [record, record]}),
            encoding="utf-8",
        )

        with pytest.raises(ClassroomActionLedgerValidationError, match="duplicate"):
            ClassroomActionLedgerRepository(path).load()

    def test_directory_at_ledger_path_fails_closed(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.json"
        path.mkdir()

        with pytest.raises(ClassroomActionLedgerValidationError, match="regular file"):
            ClassroomActionLedgerRepository(path).load()

    def test_unwritable_parent_is_reported_without_a_partial_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "private" / "ledger.json"
        repository = ClassroomActionLedgerRepository(path)

        def refuse_replace(_source: Path, _destination: Path) -> None:
            raise OSError("simulated refusal")

        monkeypatch.setattr(Path, "replace", refuse_replace)

        with pytest.raises(ClassroomActionLedgerPersistenceError, match="atomically"):
            repository.append(make_record())
        assert not path.exists()
        assert not list(path.parent.glob("*.tmp"))

    def test_reloaded_ledger_makes_repeat_a_no_op(self, tmp_path: Path) -> None:
        plan = make_plan()
        record = make_record(identity_key=plan.identity_key)
        path = tmp_path / "private" / "ledger.json"
        ClassroomActionLedgerRepository(path).append(record)

        decision = ClassroomActionAuthorizer(build_default_agent_framework()).authorize(
            plan=plan,
            approval=ClassroomActionApproval(
                approved_by="Alcy Torres",
                approved_at=NOW,
                content_fingerprint=plan.content_fingerprint,
            ),
            applied_actions=ClassroomActionLedgerRepository(path).load(),
        )

        assert decision.status is ClassroomActionStatus.ALREADY_APPLIED
        assert decision.existing_reference == "coursework-456"
