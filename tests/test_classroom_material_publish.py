"""Authorization and writer tests for controlled Classroom material publication."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.domain.agents import AgentPillar, AutonomyLevel
from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,
    GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,
    ClassroomAccessDecision,
    ClassroomAccessRequest,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_action import (
    ClassroomActionApproval,
    ClassroomActionRecord,
    ClassroomActionStatus,
)
from medsemiotics.domain.classroom_material import (
    ClassroomMaterialPackagePlan,
    ClassroomMaterialResource,
    MaterialResourceType,
)
from medsemiotics.integrations.google_classroom import (
    AppsScriptCourseworkMaterialWriter,
    AppsScriptDeployment,
    GoogleClassroomBoundaryError,
)
from medsemiotics.services.classroom_access_policy import ClassroomAccessPolicy
from medsemiotics.services.classroom_material_publish import ClassroomMaterialPublishAuthorizer

NOW = datetime(2026, 8, 30, 5, 30, tzinfo=UTC)
WEB_APP_URL = "https://script.google.com/macros/s/deployment/exec"


def make_plan(**updates: object) -> ClassroomMaterialPackagePlan:
    values: dict[str, object] = {
        "semester_id": "2026-2",
        "course_code": "GASTRO",
        "external_course_id": "course-456",
        "topic_id": "gastro-intro-workflow",
        "title": "Material de aproximación gastroenterológica",
        "description": "Revisar antes de la clase.",
        "folder_url": "https://drive.google.com/drive/folders/folder-456",
        "resources": (
            ClassroomMaterialResource(
                resource_type=MaterialResourceType.PPTX,
                title="Presentación",
                url="https://docs.google.com/presentation/d/presentation-1/edit",
            ),
        ),
        "prepared_by": "faculty-owner",
        "prepared_at": NOW,
    }
    values.update(updates)
    return ClassroomMaterialPackagePlan(**values)  # type: ignore[arg-type]


def make_approval(plan: ClassroomMaterialPackagePlan) -> ClassroomActionApproval:
    return ClassroomActionApproval(
        approved_by="Alcy Torres",
        approved_at=NOW,
        content_fingerprint=plan.content_fingerprint,
    )


def make_access(**updates: object) -> ClassroomAccessDecision:
    values: dict[str, object] = {
        "allowed": True,
        "operation": ClassroomOperation.COURSEWORK_MATERIAL_PUBLISH,
        "approved_data_categories": (ClassroomDataCategory.OWN_COURSEWORK_MATERIAL,),
        "approved_oauth_scopes": (GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,),
        "reason": "One material package is permitted.",
    }
    values.update(updates)
    return ClassroomAccessDecision(**values)  # type: ignore[arg-type]


def make_envelope(**material_updates: object) -> dict[str, Any]:
    material: dict[str, Any] = {
        "id": "material-789",
        "state": "PUBLISHED",
        "alternate_link": "https://classroom.google.com/c/course-456/m/material-789",
        "material_count": 2,
    }
    material.update(material_updates)
    return {
        "operation": "coursework_material_publish",
        "scopes": [GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE],
        "external_mutation": True,
        "coursework_material": material,
    }


class FakeTransport:
    def __init__(self, envelope: Mapping[str, Any] | None = None) -> None:
        self.envelope = envelope or make_envelope()
        self.calls: list[tuple[str, str, Mapping[str, Any]]] = []

    def submit(self, *, url: str, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((url, operation, dict(payload)))
        return self.envelope


def make_writer(transport: FakeTransport) -> AppsScriptCourseworkMaterialWriter:
    return AppsScriptCourseworkMaterialWriter(
        deployment=AppsScriptDeployment(deployment_id="deployment", web_app_url=WEB_APP_URL),
        transport=transport,
        clock=lambda: NOW,
    )


class TestMaterialAccessPolicy:
    def test_grants_only_the_exact_material_scope(self) -> None:
        decision = ClassroomAccessPolicy().authorize(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSEWORK_MATERIAL_PUBLISH,
                data_categories=(ClassroomDataCategory.OWN_COURSEWORK_MATERIAL,),
                oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,),
                requested_by="faculty-owner",
                external_mutation=True,
            )
        )

        assert decision.allowed is True

    @pytest.mark.parametrize(
        ("categories", "scopes"),
        [
            ((ClassroomDataCategory.GRADES,), (GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,)),
            (
                (ClassroomDataCategory.OWN_COURSEWORK_MATERIAL,),
                (GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
            ),
        ],
    )
    def test_denies_broader_data_or_wrong_scope(
        self,
        categories: tuple[ClassroomDataCategory, ...],
        scopes: tuple[str, ...],
    ) -> None:
        decision = ClassroomAccessPolicy().evaluate(
            ClassroomAccessRequest(
                operation=ClassroomOperation.COURSEWORK_MATERIAL_PUBLISH,
                data_categories=categories,
                oauth_scopes=scopes,
                requested_by="faculty-owner",
                external_mutation=True,
            )
        )

        assert decision.allowed is False
        assert decision.approved_oauth_scopes == ()


class TestMaterialAuthorizer:
    def test_authorizes_exact_approved_content(self) -> None:
        plan = make_plan()
        decision = ClassroomMaterialPublishAuthorizer(build_default_agent_framework()).authorize(
            plan=plan, approval=make_approval(plan)
        )

        assert decision.status is ClassroomActionStatus.AUTHORIZED
        assert decision.approved_by == "Alcy Torres"

    def test_edited_content_is_denied(self) -> None:
        plan = make_plan()
        edited = make_plan(description="Edited after approval")
        decision = ClassroomMaterialPublishAuthorizer(build_default_agent_framework()).authorize(
            plan=edited, approval=make_approval(plan)
        )

        assert decision.status is ClassroomActionStatus.DENIED

    def test_persistent_record_makes_repeat_a_no_op(self) -> None:
        plan = make_plan()
        record = ClassroomActionRecord(
            identity_key=plan.identity_key,
            external_course_id=plan.external_course_id,
            applied_at=NOW,
            applied_by="Alcy Torres",
            external_reference="material-789",
        )
        decision = ClassroomMaterialPublishAuthorizer(build_default_agent_framework()).authorize(
            plan=plan, approval=make_approval(plan), applied_actions=(record,)
        )

        assert decision.status is ClassroomActionStatus.ALREADY_APPLIED
        assert decision.existing_reference == "material-789"

    def test_capability_requires_named_approval_and_is_not_automation(self) -> None:
        capability = build_default_agent_framework().get_capability(
            AgentPillar.COORDINATION,
            "coordination.classroom-material-publish",
        )

        assert capability.minimum_autonomy is AutonomyLevel.EXECUTE_WITH_APPROVAL
        assert capability.maximum_autonomy is AutonomyLevel.EXECUTE_WITH_APPROVAL
        assert capability.trusted_automation_eligible is False


class TestMaterialWriter:
    def test_publishes_exact_package_and_returns_ledger_record(self) -> None:
        plan = make_plan()
        decision = ClassroomMaterialPublishAuthorizer(build_default_agent_framework()).authorize(
            plan=plan, approval=make_approval(plan)
        )
        transport = FakeTransport()

        record = make_writer(transport).publish(
            plan=plan,
            action_decision=decision,
            access_decision=make_access(),
        )

        url, operation, payload = transport.calls[0]
        assert url == WEB_APP_URL
        assert operation == "coursework_material_publish"
        assert payload["folder_url"] == plan.folder_url
        assert payload["resources"] == [plan.resources[0].model_dump(mode="json")]
        assert "student_ids" not in payload
        assert "grade" not in payload
        assert record.external_reference == "material-789"
        assert record.applied_by == "Alcy Torres"

    @pytest.mark.parametrize(
        "access",
        [
            make_access(allowed=False, approved_data_categories=(), approved_oauth_scopes=()),
            make_access(
                operation=ClassroomOperation.COURSEWORK_DRAFT_CREATE,
                approved_data_categories=(ClassroomDataCategory.OWN_COURSEWORK_DRAFT,),
                approved_oauth_scopes=(GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
            ),
        ],
    )
    def test_refuses_wrong_access_before_transport(self, access: ClassroomAccessDecision) -> None:
        plan = make_plan()
        decision = ClassroomMaterialPublishAuthorizer(build_default_agent_framework()).authorize(
            plan=plan, approval=make_approval(plan)
        )
        transport = FakeTransport()

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(transport).publish(
                plan=plan,
                action_decision=decision,
                access_decision=access,
            )
        assert transport.calls == []

    @pytest.mark.parametrize(
        "envelope",
        [make_envelope(state="DRAFT"), make_envelope(material_count=1)],
    )
    def test_refuses_reply_outside_approved_publication(self, envelope: Mapping[str, Any]) -> None:
        plan = make_plan()
        decision = ClassroomMaterialPublishAuthorizer(build_default_agent_framework()).authorize(
            plan=plan, approval=make_approval(plan)
        )

        with pytest.raises(GoogleClassroomBoundaryError):
            make_writer(FakeTransport(envelope)).publish(
                plan=plan,
                action_decision=decision,
                access_decision=make_access(),
            )
