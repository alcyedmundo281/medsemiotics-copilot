"""Tests for the Loop 0.6F approved Classroom coursework draft write."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import pytest

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,
    ClassroomAccessDecision,
    ClassroomAccessRequest,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_action import (
    ClassroomActionDecision,
    ClassroomActionPlan,
    ClassroomActionStatus,
    ClassroomActionType,
)
from medsemiotics.domain.exceptions import ClassroomAccessPolicyError
from medsemiotics.integrations.google_classroom import (
    AppsScriptCourseworkWriter,
    AppsScriptDeployment,
    GoogleClassroomBoundaryError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
)
from medsemiotics.services.classroom_access_policy import ClassroomAccessPolicy

WEB_APP_URL = "https://script.google.com/macros/s/AKfycb-deployment/exec"
APPLIED_AT = datetime(2026, 8, 30, 12, 30, tzinfo=UTC)


def make_plan(**updates: object) -> ClassroomActionPlan:
    """Build the approved coursework draft plan."""
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
        "prepared_at": APPLIED_AT,
    }
    values.update(updates)
    return ClassroomActionPlan(**values)  # type: ignore[arg-type]


def make_action_decision(plan: ClassroomActionPlan, **updates: object) -> ClassroomActionDecision:
    """Build the Loop 0.6E decision authorizing this plan."""
    values: dict[str, object] = {
        "status": ClassroomActionStatus.AUTHORIZED,
        "action_type": ClassroomActionType.CREATE_COURSEWORK_DRAFT,
        "identity_key": plan.identity_key,
        "approved_by": "department-head",
        "reason": "One coursework draft is authorized for the reviewed content.",
    }
    values.update(updates)
    return ClassroomActionDecision(**values)  # type: ignore[arg-type]


def make_access_decision(**updates: object) -> ClassroomAccessDecision:
    """Build the Loop 0.6A decision authorizing the write scope."""
    values: dict[str, object] = {
        "allowed": True,
        "operation": ClassroomOperation.COURSEWORK_DRAFT_CREATE,
        "approved_data_categories": (ClassroomDataCategory.OWN_COURSEWORK_DRAFT,),
        "approved_oauth_scopes": (GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
        "reason": "Creating one coursework draft is permitted.",
    }
    values.update(updates)
    return ClassroomAccessDecision(**values)  # type: ignore[arg-type]


def make_envelope(**updates: object) -> dict[str, Any]:
    """Build the only write reply the contract accepts."""
    envelope: dict[str, Any] = {
        "operation": "coursework_draft_create",
        "scopes": [GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE],
        "external_mutation": True,
        "coursework": {
            "id": "coursework-991",
            "state": "DRAFT",
            "alternate_link": "https://classroom.google.com/c/770001/a/991",
        },
    }
    envelope.update(updates)
    return envelope


class FakeWriteTransport:
    """Record submissions without performing any network request."""

    def __init__(
        self,
        envelope: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.envelope = envelope if envelope is not None else make_envelope()
        self.error = error
        self.calls: list[tuple[str, str, Mapping[str, Any]]] = []

    def submit(
        self,
        *,
        url: str,
        operation: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Record the submission and return the configured envelope."""
        self.calls.append((url, operation, dict(payload)))
        if self.error is not None:
            raise self.error
        return self.envelope


def make_writer(transport: FakeWriteTransport) -> AppsScriptCourseworkWriter:
    """Build the write boundary with a deterministic clock."""
    return AppsScriptCourseworkWriter(
        deployment=AppsScriptDeployment(
            deployment_id="AKfycb-deployment",
            web_app_url=WEB_APP_URL,
        ),
        transport=transport,
        clock=lambda: APPLIED_AT,
    )


class TestUnknownOperations:
    """Verify an operation outside the contract is denied rather than assumed."""

    def test_denies_an_operation_the_contract_does_not_declare(self) -> None:
        request = ClassroomAccessRequest(
            operation=ClassroomOperation.COURSE_DISCOVERY,
            data_categories=(ClassroomDataCategory.COURSE_METADATA,),
            oauth_scopes=(GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,),
            requested_by="course-director",
            external_mutation=False,
        ).model_copy(update={"operation": "delete_course"})

        with pytest.raises(ClassroomAccessPolicyError) as err:
            ClassroomAccessPolicy().evaluate(request)

        assert "not part of the Classroom contract" in str(err.value)


class TestWritePolicyExtension:
    """Verify the access policy grants exactly one write and nothing else."""

    def test_authorizes_the_declared_write(self) -> None:
        decision = ClassroomAccessPolicy().authorize(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSEWORK_DRAFT_CREATE,
                data_categories=(ClassroomDataCategory.OWN_COURSEWORK_DRAFT,),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
                requested_by="course-director",
                external_mutation=True,
            )
        )

        assert decision.allowed is True
        assert decision.approved_oauth_scopes == (GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,)

    def test_denies_the_write_declared_as_read_only(self) -> None:
        with pytest.raises(ClassroomAccessPolicyError, match="must be declared as a mutation"):
            ClassroomAccessPolicy().authorize(
                ClassroomAccessRequest(
                    operation=ClassroomOperation.COURSEWORK_DRAFT_CREATE,
                    data_categories=(ClassroomDataCategory.OWN_COURSEWORK_DRAFT,),
                    oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
                    requested_by="course-director",
                    external_mutation=False,
                )
            )

    @pytest.mark.parametrize(
        "category",
        [
            ClassroomDataCategory.GRADES,
            ClassroomDataCategory.SUBMISSIONS,
            ClassroomDataCategory.ROSTERS,
            ClassroomDataCategory.COURSEWORK,
        ],
    )
    def test_denies_any_additional_category_on_the_write(
        self,
        category: ClassroomDataCategory,
    ) -> None:
        decision = ClassroomAccessPolicy().evaluate(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSEWORK_DRAFT_CREATE,
                data_categories=(ClassroomDataCategory.OWN_COURSEWORK_DRAFT, category),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
                requested_by="course-director",
                external_mutation=True,
            )
        )

        assert decision.allowed is False
        assert decision.approved_oauth_scopes == ()

    def test_denies_the_read_scope_for_the_write_operation(self) -> None:
        decision = ClassroomAccessPolicy().evaluate(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSEWORK_DRAFT_CREATE,
                data_categories=(ClassroomDataCategory.OWN_COURSEWORK_DRAFT,),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,),
                requested_by="course-director",
                external_mutation=True,
            )
        )

        assert decision.allowed is False

    def test_keeps_discovery_read_only(self) -> None:
        decision = ClassroomAccessPolicy().evaluate(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSE_DISCOVERY,
                data_categories=(ClassroomDataCategory.COURSE_METADATA,),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
                requested_by="course-director",
                external_mutation=False,
            )
        )

        assert decision.allowed is False
        assert "classroom.courses.readonly" in decision.reason


class TestApprovedWrite:
    """Verify one approved draft is applied and recorded for future idempotency."""

    def test_applies_the_draft_and_returns_the_ledger_entry(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport()

        record = make_writer(transport).create_coursework_draft(
            plan=plan,
            action_decision=make_action_decision(plan),
            access_decision=make_access_decision(),
        )

        url, operation, payload = transport.calls[0]
        assert url == WEB_APP_URL
        assert operation == "coursework_draft_create"
        assert payload == {
            "course_id": "770001",
            "title": plan.title,
            "instructions": plan.instructions,
            "due_date": "2026-09-12",
            "identity_key": plan.identity_key,
        }
        assert record.identity_key == plan.identity_key
        assert record.external_course_id == "770001"
        assert record.external_reference == "coursework-991"
        assert record.applied_by == "department-head"
        assert record.applied_at == APPLIED_AT

    def test_sends_no_grading_field(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport()

        make_writer(transport).create_coursework_draft(
            plan=plan,
            action_decision=make_action_decision(plan),
            access_decision=make_access_decision(),
        )

        sent = transport.calls[0][2]
        for prohibited in ("max_points", "maxPoints", "grade", "assigned_students", "state"):
            assert prohibited not in sent

    def test_omits_an_absent_due_date(self) -> None:
        plan = make_plan(due_date=None, instructions=None)
        transport = FakeWriteTransport()

        make_writer(transport).create_coursework_draft(
            plan=plan,
            action_decision=make_action_decision(plan),
            access_decision=make_access_decision(),
        )

        assert transport.calls[0][2]["due_date"] == ""
        assert transport.calls[0][2]["instructions"] == ""


class TestWriteAuthorizationGuards:
    """Verify nothing is sent without both decisions matching this exact plan."""

    def test_refuses_a_denied_access_decision(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport()

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(transport).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(
                    allowed=False,
                    approved_data_categories=(),
                    approved_oauth_scopes=(),
                    reason="Denied.",
                ),
            )

        assert transport.calls == []

    def test_refuses_a_read_only_access_decision(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport()

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(transport).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(
                    operation=ClassroomOperation.COURSE_DISCOVERY,
                    approved_data_categories=(ClassroomDataCategory.COURSE_METADATA,),
                    approved_oauth_scopes=(GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,),
                ),
            )

        assert transport.calls == []

    def test_refuses_broader_approved_authority(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport()

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(transport).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(
                    approved_data_categories=(
                        ClassroomDataCategory.OWN_COURSEWORK_DRAFT,
                        ClassroomDataCategory.GRADES,
                    )
                ),
            )

        assert transport.calls == []

    @pytest.mark.parametrize(
        "status",
        [ClassroomActionStatus.ALREADY_APPLIED, ClassroomActionStatus.DENIED],
    )
    def test_refuses_an_action_decision_that_is_not_authorized(
        self,
        status: ClassroomActionStatus,
    ) -> None:
        plan = make_plan()
        transport = FakeWriteTransport()

        with pytest.raises(GoogleClassroomBoundaryError) as err:
            make_writer(transport).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(
                    plan,
                    status=status,
                    approved_by=None,
                    reason="Not authorized now.",
                ),
                access_decision=make_access_decision(),
            )

        assert status.value in str(err.value)
        assert transport.calls == []

    def test_refuses_a_decision_for_a_different_plan(self) -> None:
        transport = FakeWriteTransport()
        other_plan = make_plan(title="Otro taller distinto")

        with pytest.raises(GoogleClassroomBoundaryError) as err:
            make_writer(transport).create_coursework_draft(
                plan=make_plan(),
                action_decision=make_action_decision(other_plan),
                access_decision=make_access_decision(),
            )

        assert "different plan" in str(err.value)
        assert transport.calls == []

    def test_refuses_an_action_outside_the_write_contract(self) -> None:
        plan = make_plan()
        forged = plan.model_copy(update={"action_type": "publish_grades"})
        transport = FakeWriteTransport()

        with pytest.raises(GoogleClassroomBoundaryError) as err:
            make_writer(transport).create_coursework_draft(
                plan=forged,
                action_decision=make_action_decision(plan).model_copy(
                    update={"identity_key": forged.identity_key}
                ),
                access_decision=make_access_decision(),
            )

        assert "publish_grades" in str(err.value)
        assert transport.calls == []

    def test_refuses_a_broader_approved_scope(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport()

        with pytest.raises(GoogleClassroomBoundaryError) as err:
            make_writer(transport).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(
                    approved_oauth_scopes=(
                        GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,
                        "https://www.googleapis.com/auth/classroom.rosters",
                    )
                ),
            )

        assert "exactly" in str(err.value)
        assert transport.calls == []


class TestWriteReplyBoundary:
    """Verify a published item, a grading field, or an unusable reply fails closed."""

    def test_refuses_a_published_item(self) -> None:
        envelope = make_envelope()
        envelope["coursework"]["state"] = "PUBLISHED"
        plan = make_plan()

        with pytest.raises(GoogleClassroomBoundaryError) as err:
            make_writer(FakeWriteTransport(envelope)).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

        assert "never publishes coursework" in str(err.value)

    @pytest.mark.parametrize("prohibited", ["maxPoints", "assignedGrade", "grade", "submissions"])
    def test_refuses_a_grading_field_in_the_reply(self, prohibited: str) -> None:
        envelope = make_envelope()
        envelope["coursework"][prohibited] = 10
        plan = make_plan()

        with pytest.raises(GoogleClassroomBoundaryError) as err:
            make_writer(FakeWriteTransport(envelope)).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

        assert prohibited in str(err.value)

    def test_refuses_an_unrecognized_reply_field(self) -> None:
        envelope = make_envelope()
        envelope["coursework"]["scheduledTime"] = "2026-09-01T00:00:00Z"
        plan = make_plan()

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(FakeWriteTransport(envelope)).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_refuses_a_reply_that_denies_the_mutation(self) -> None:
        plan = make_plan()

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(
                FakeWriteTransport(make_envelope(external_mutation=False))
            ).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_refuses_a_reply_declaring_a_broader_scope(self) -> None:
        plan = make_plan()
        envelope = make_envelope(
            scopes=[
                GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,
                "https://www.googleapis.com/auth/classroom.rosters",
            ]
        )

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(FakeWriteTransport(envelope)).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_refuses_a_reply_for_another_operation(self) -> None:
        plan = make_plan()

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(
                FakeWriteTransport(make_envelope(operation="course_discovery"))
            ).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_refuses_an_incomplete_reply(self) -> None:
        envelope = make_envelope()
        del envelope["scopes"]
        plan = make_plan()

        with pytest.raises(GoogleClassroomReadError):
            make_writer(FakeWriteTransport(envelope)).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    @pytest.mark.parametrize("malformed", ["not-an-object", ["coursework"], None])
    def test_refuses_a_malformed_coursework_object(self, malformed: object) -> None:
        plan = make_plan()

        with pytest.raises(GoogleClassroomReadError):
            make_writer(
                FakeWriteTransport(make_envelope(coursework=malformed))
            ).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_refuses_a_reply_that_is_not_an_object(self) -> None:
        plan = make_plan()

        with pytest.raises(GoogleClassroomReadError):
            make_writer(FakeWriteTransport(["created"])).create_coursework_draft(  # type: ignore[arg-type]
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_refuses_a_draft_without_an_identifier(self) -> None:
        envelope = make_envelope()
        envelope["coursework"]["id"] = "   "
        plan = make_plan()

        with pytest.raises(GoogleClassroomMappingError):
            make_writer(FakeWriteTransport(envelope)).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_wraps_transport_failures_without_leaking_details(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport(error=TimeoutError(f"failed to reach {WEB_APP_URL}"))

        with pytest.raises(GoogleClassroomReadError) as err:
            make_writer(transport).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

        assert WEB_APP_URL not in str(err.value)
        assert err.value.__cause__ is None

    def test_propagates_a_boundary_failure_from_the_transport(self) -> None:
        plan = make_plan()
        transport = FakeWriteTransport(
            error=GoogleClassroomBoundaryError("the deployment refused the payload")
        )

        with pytest.raises(GoogleClassroomBoundaryError, match="refused the payload"):
            make_writer(transport).create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )

    def test_refuses_to_record_an_unaccountable_application(self) -> None:
        plan = make_plan()
        decision = make_action_decision(plan).model_copy(update={"approved_by": "   "})

        with pytest.raises(GoogleClassroomMappingError, match="could not be recorded"):
            make_writer(FakeWriteTransport()).create_coursework_draft(
                plan=plan,
                action_decision=decision,
                access_decision=make_access_decision(),
            )

    def test_rejects_a_naive_clock(self) -> None:
        plan = make_plan()
        writer = AppsScriptCourseworkWriter(
            deployment=AppsScriptDeployment(
                deployment_id="AKfycb-deployment",
                web_app_url=WEB_APP_URL,
            ),
            transport=FakeWriteTransport(),
            clock=lambda: datetime(2026, 8, 30, 12, 30),
        )

        with pytest.raises(GoogleClassroomMappingError):
            writer.create_coursework_draft(
                plan=plan,
                action_decision=make_action_decision(plan),
                access_decision=make_access_decision(),
            )
