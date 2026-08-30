"""Apply exactly one approved Classroom coursework draft through the Apps Script deployment.

The deployment holds the write authority; MedSemiotics holds none. This adapter re-verifies both
the Loop 0.6A access decision and the Loop 0.6E action decision before it sends anything, sends
only allowlisted fields, and refuses any answer that reports a published item or a grading field.
"""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,
    ClassroomAccessDecision,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_action import (
    ClassroomActionDecision,
    ClassroomActionPlan,
    ClassroomActionRecord,
    ClassroomActionStatus,
    ClassroomActionType,
)
from medsemiotics.integrations.google_classroom.apps_script import (
    AppsScriptDeployment,
    reject_unexpected_keys,
)
from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomBoundaryError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
)

COURSEWORK_DRAFT_OPERATION = ClassroomOperation.COURSEWORK_DRAFT_CREATE.value

DRAFT_STATE = "DRAFT"

ALLOWED_WRITE_ENVELOPE_KEYS = frozenset({"operation", "scopes", "external_mutation", "coursework"})
ALLOWED_COURSEWORK_KEYS = frozenset({"id", "state", "alternate_link"})


class AppsScriptWriteTransport(Protocol):
    """Minimal write transport contract for the Apps Script web app."""

    def submit(
        self,
        *,
        url: str,
        operation: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Send one write operation and return the decoded JSON envelope."""
        ...


class AppsScriptCourseworkWriter:
    """Create one approved coursework draft and return the ledger entry it produced."""

    _REQUIRED_CATEGORIES = (ClassroomDataCategory.OWN_COURSEWORK_DRAFT,)
    _REQUIRED_SCOPES = (GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,)

    def __init__(
        self,
        *,
        deployment: AppsScriptDeployment,
        transport: AppsScriptWriteTransport,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the write boundary with an injected transport and clock."""
        self._deployment = deployment
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_coursework_draft(
        self,
        *,
        plan: ClassroomActionPlan,
        action_decision: ClassroomActionDecision,
        access_decision: ClassroomAccessDecision,
    ) -> ClassroomActionRecord:
        """Apply one authorized coursework draft.

        Args:
            plan: The single action that was reviewed and approved.
            action_decision: Loop 0.6E decision authorizing exactly this plan.
            access_decision: Loop 0.6A decision authorizing the write operation and scope.

        Returns:
            The ClassroomActionRecord that makes a repeat of this plan a no-op.

        Raises:
            GoogleClassroomBoundaryError: If authorization is missing, mismatched, or too broad,
                or if the deployment reports anything outside the draft contract.
            GoogleClassroomReadError: If the deployment cannot be reached or answers unusably.
            GoogleClassroomMappingError: If the reported draft cannot be recorded.
        """
        self._verify_access_decision(access_decision)
        self._verify_action_decision(plan, action_decision)

        payload: dict[str, Any] = {
            "course_id": plan.external_course_id,
            "title": plan.title,
            "instructions": plan.instructions or "",
            "due_date": plan.due_date.isoformat() if plan.due_date else "",
            "identity_key": plan.identity_key,
        }

        try:
            envelope = self._transport.submit(
                url=self._deployment.web_app_url,
                operation=COURSEWORK_DRAFT_OPERATION,
                payload=payload,
            )
        except (GoogleClassroomReadError, GoogleClassroomBoundaryError):
            raise
        except Exception as err:
            msg = (
                "Failed to apply the Classroom coursework draft through the configured "
                f"deployment ({type(err).__name__}); transport details are withheld."
            )
            raise GoogleClassroomReadError(msg) from None

        coursework = self._verify_envelope(envelope)
        approved_by = action_decision.approved_by
        if approved_by is None:  # pragma: no cover - guaranteed by the decision model
            msg = "An authorized action decision must record its approver."
            raise GoogleClassroomBoundaryError(msg)

        try:
            return ClassroomActionRecord(
                identity_key=plan.identity_key,
                external_course_id=plan.external_course_id,
                applied_at=self._applied_at(),
                applied_by=approved_by,
                external_reference=coursework.get("id"),
            )
        except ValueError as err:
            msg = f"The applied Classroom draft could not be recorded: {err}"
            raise GoogleClassroomMappingError(msg) from None

    def _verify_access_decision(self, decision: ClassroomAccessDecision) -> None:
        """Fail closed before contacting Google when write authority is absent or too broad."""
        if not decision.allowed:
            msg = f"Creating a coursework draft is not authorized: {decision.reason}"
            raise GoogleClassroomBoundaryError(msg)
        if decision.operation.value != COURSEWORK_DRAFT_OPERATION:
            msg = (
                "The Classroom access decision authorizes "
                f"'{decision.operation.value}', not creating a coursework draft."
            )
            raise GoogleClassroomBoundaryError(msg)
        if decision.approved_data_categories != self._REQUIRED_CATEGORIES:
            msg = (
                "Creating a coursework draft requires an approval limited to own_coursework_draft."
            )
            raise GoogleClassroomBoundaryError(msg)
        if decision.approved_oauth_scopes != self._REQUIRED_SCOPES:
            msg = (
                "Creating a coursework draft requires exactly the "
                "classroom.coursework.students OAuth scope."
            )
            raise GoogleClassroomBoundaryError(msg)

    @staticmethod
    def _verify_action_decision(
        plan: ClassroomActionPlan,
        decision: ClassroomActionDecision,
    ) -> None:
        """Refuse to apply anything but the exact plan a named approver authorized."""
        if decision.status is not ClassroomActionStatus.AUTHORIZED:
            msg = (
                f"The action decision is '{decision.status.value}', not authorized: "
                f"{decision.reason}"
            )
            raise GoogleClassroomBoundaryError(msg)
        if decision.identity_key != plan.identity_key:
            msg = "The action decision authorizes a different plan than the one supplied."
            raise GoogleClassroomBoundaryError(msg)
        if str(plan.action_type) != ClassroomActionType.CREATE_COURSEWORK_DRAFT.value:
            msg = (
                f"Plan action '{plan.action_type}' is outside the coursework-draft write contract."
            )
            raise GoogleClassroomBoundaryError(msg)

    def _verify_envelope(self, envelope: object) -> Mapping[str, Any]:
        """Validate the write reply and return the reported draft."""
        if not isinstance(envelope, Mapping):
            msg = f"Apps Script reply must be a JSON object, got {type(envelope).__name__}"
            raise GoogleClassroomReadError(msg)

        reject_unexpected_keys(envelope.keys(), ALLOWED_WRITE_ENVELOPE_KEYS, "write reply")
        missing = sorted(ALLOWED_WRITE_ENVELOPE_KEYS - set(envelope.keys()))
        if missing:
            msg = f"Apps Script write reply is missing required fields: {', '.join(missing)}"
            raise GoogleClassroomReadError(msg)

        if envelope["operation"] != COURSEWORK_DRAFT_OPERATION:
            msg = (
                "Apps Script reply declares operation "
                f"'{envelope['operation']}', not '{COURSEWORK_DRAFT_OPERATION}'."
            )
            raise GoogleClassroomBoundaryError(msg)

        if envelope["external_mutation"] is not True:
            msg = "Apps Script write reply must declare external_mutation=true."
            raise GoogleClassroomBoundaryError(msg)

        scopes = envelope["scopes"]
        if not isinstance(scopes, list | tuple) or tuple(scopes) != self._REQUIRED_SCOPES:
            msg = (
                "Apps Script write reply must declare exactly the "
                "classroom.coursework.students OAuth scope."
            )
            raise GoogleClassroomBoundaryError(msg)

        coursework = envelope["coursework"]
        if not isinstance(coursework, Mapping):
            msg = (
                "Apps Script write reply 'coursework' must be a JSON object, got "
                f"{type(coursework).__name__}"
            )
            raise GoogleClassroomReadError(msg)

        reject_unexpected_keys(coursework.keys(), ALLOWED_COURSEWORK_KEYS, "created coursework")

        state = coursework.get("state")
        if state != DRAFT_STATE:
            msg = (
                f"The deployment reported coursework in state '{state}', not {DRAFT_STATE}; "
                "MedSemiotics never publishes coursework to students."
            )
            raise GoogleClassroomBoundaryError(msg)

        identifier = coursework.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            msg = "The deployment reported a created draft without an identifier."
            raise GoogleClassroomMappingError(msg)
        return coursework

    def _applied_at(self) -> datetime:
        """Obtain a timezone-aware application timestamp for the ledger."""
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
            msg = "Classroom writer clock must return a timezone-aware timestamp"
            raise GoogleClassroomMappingError(msg)
        return timestamp
