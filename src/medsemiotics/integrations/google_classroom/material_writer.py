"""Publish one approved, folder-backed course material through Apps Script."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,
    ClassroomAccessDecision,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_action import (
    ClassroomActionDecision,
    ClassroomActionRecord,
    ClassroomActionStatus,
    ClassroomActionType,
)
from medsemiotics.domain.classroom_material import ClassroomMaterialPackagePlan
from medsemiotics.integrations.google_classroom.apps_script import (
    AppsScriptDeployment,
    reject_unexpected_keys,
)
from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomBoundaryError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
)
from medsemiotics.integrations.google_classroom.writer import AppsScriptWriteTransport

MATERIAL_PUBLISH_OPERATION = ClassroomOperation.COURSEWORK_MATERIAL_PUBLISH.value
PUBLISHED_STATE = "PUBLISHED"
ALLOWED_MATERIAL_ENVELOPE_KEYS = frozenset(
    {"operation", "scopes", "external_mutation", "coursework_material"}
)
ALLOWED_MATERIAL_REPLY_KEYS = frozenset({"id", "state", "alternate_link", "material_count"})


class AppsScriptCourseworkMaterialWriter:
    """Publish exactly one student-visible package after both policy decisions pass."""

    _REQUIRED_CATEGORIES = (ClassroomDataCategory.OWN_COURSEWORK_MATERIAL,)
    _REQUIRED_SCOPES = (GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,)

    def __init__(
        self,
        *,
        deployment: AppsScriptDeployment,
        transport: AppsScriptWriteTransport,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._deployment = deployment
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    def publish(
        self,
        *,
        plan: ClassroomMaterialPackagePlan,
        action_decision: ClassroomActionDecision,
        access_decision: ClassroomAccessDecision,
    ) -> ClassroomActionRecord:
        """Publish the exact approved package and return its private ledger record."""
        self._verify_access(access_decision)
        self._verify_action(plan, action_decision)

        payload: dict[str, Any] = {
            "course_id": plan.external_course_id,
            "title": plan.title,
            "description": plan.description or "",
            "folder_url": plan.folder_url,
            "resources": [resource.model_dump(mode="json") for resource in plan.resources],
            "identity_key": plan.identity_key,
        }
        try:
            envelope = self._transport.submit(
                url=self._deployment.web_app_url,
                operation=MATERIAL_PUBLISH_OPERATION,
                payload=payload,
            )
        except (GoogleClassroomReadError, GoogleClassroomBoundaryError):
            raise
        except Exception as err:
            msg = (
                "Failed to publish the Classroom material package through the configured "
                f"deployment ({type(err).__name__}); transport details are withheld."
            )
            raise GoogleClassroomReadError(msg) from None

        material = self._verify_envelope(envelope, expected_count=1 + len(plan.resources))
        approved_by = action_decision.approved_by
        if approved_by is None:  # pragma: no cover - guaranteed by decision model
            msg = "An authorized material publication must record its approver."
            raise GoogleClassroomBoundaryError(msg)
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
            msg = "Classroom material writer clock must return a timezone-aware timestamp."
            raise GoogleClassroomMappingError(msg)
        try:
            return ClassroomActionRecord(
                identity_key=plan.identity_key,
                external_course_id=plan.external_course_id,
                applied_at=timestamp,
                applied_by=approved_by,
                external_reference=material.get("id"),
            )
        except ValueError as err:
            msg = f"The published Classroom material could not be recorded: {err}"
            raise GoogleClassroomMappingError(msg) from None

    def _verify_access(self, decision: ClassroomAccessDecision) -> None:
        if not decision.allowed:
            msg = f"Publishing course material is not authorized: {decision.reason}"
            raise GoogleClassroomBoundaryError(msg)
        if decision.operation is not ClassroomOperation.COURSEWORK_MATERIAL_PUBLISH:
            msg = "The access decision does not authorize course material publication."
            raise GoogleClassroomBoundaryError(msg)
        if decision.approved_data_categories != self._REQUIRED_CATEGORIES:
            msg = "Material publication requires approval limited to own_coursework_material."
            raise GoogleClassroomBoundaryError(msg)
        if decision.approved_oauth_scopes != self._REQUIRED_SCOPES:
            msg = "Material publication requires exactly the classroom.courseworkmaterials scope."
            raise GoogleClassroomBoundaryError(msg)

    @staticmethod
    def _verify_action(
        plan: ClassroomMaterialPackagePlan,
        decision: ClassroomActionDecision,
    ) -> None:
        if decision.status is not ClassroomActionStatus.AUTHORIZED:
            msg = f"The material publication decision is '{decision.status.value}', not authorized."
            raise GoogleClassroomBoundaryError(msg)
        if decision.identity_key != plan.identity_key:
            msg = "The action decision authorizes a different material package."
            raise GoogleClassroomBoundaryError(msg)
        if decision.action_type is not ClassroomActionType.PUBLISH_COURSEWORK_MATERIAL:
            msg = "The action decision does not authorize material publication."
            raise GoogleClassroomBoundaryError(msg)

    @staticmethod
    def _verify_envelope(envelope: object, *, expected_count: int) -> Mapping[str, Any]:
        if not isinstance(envelope, Mapping):
            msg = "Apps Script material reply must be a JSON object."
            raise GoogleClassroomReadError(msg)
        reject_unexpected_keys(
            envelope.keys(), ALLOWED_MATERIAL_ENVELOPE_KEYS, "material publish reply"
        )
        if set(envelope) != ALLOWED_MATERIAL_ENVELOPE_KEYS:
            msg = "Apps Script material reply is incomplete."
            raise GoogleClassroomReadError(msg)
        if envelope["operation"] != MATERIAL_PUBLISH_OPERATION:
            msg = "Apps Script replied for a different operation."
            raise GoogleClassroomBoundaryError(msg)
        if envelope["scopes"] != [GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE]:
            msg = "Apps Script reported an unexpected material publication scope."
            raise GoogleClassroomBoundaryError(msg)
        if envelope["external_mutation"] is not True:
            msg = "Apps Script material publication was not declared as a mutation."
            raise GoogleClassroomBoundaryError(msg)

        material = envelope["coursework_material"]
        if not isinstance(material, Mapping):
            msg = "Apps Script material result must be a JSON object."
            raise GoogleClassroomReadError(msg)
        reject_unexpected_keys(material.keys(), ALLOWED_MATERIAL_REPLY_KEYS, "material result")
        if set(material) != ALLOWED_MATERIAL_REPLY_KEYS:
            msg = "Apps Script material result is incomplete."
            raise GoogleClassroomReadError(msg)
        if material["state"] != PUBLISHED_STATE:
            msg = "Apps Script did not report a student-visible PUBLISHED material."
            raise GoogleClassroomBoundaryError(msg)
        if material["material_count"] != expected_count:
            msg = "Apps Script reported a different attachment count than the approved package."
            raise GoogleClassroomBoundaryError(msg)
        if not isinstance(material["id"], str) or not material["id"].strip():
            msg = "Apps Script material result has no usable identifier."
            raise GoogleClassroomMappingError(msg)
        return material
