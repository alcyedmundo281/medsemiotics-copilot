"""Persistent Apps Script read boundary for metadata-only Classroom course discovery.

MedSemiotics never holds a Google Classroom OAuth token. The dedicated Workspace account owns a
private Apps Script web app whose authorization persists between runs; this module consumes that
deployment through an injected transport and re-validates every payload against the Loop 0.6A
access decision before any course metadata reaches the domain.
"""

import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    ClassroomAccessDecision,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.classroom_discovery import (
    ClassroomCourseDiscovery,
    ClassroomCourseState,
    DiscoveredClassroomCourse,
)
from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomBoundaryError,
    GoogleClassroomConfigurationError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
)

APPS_SCRIPT_URL_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_URL"
APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_DEPLOYMENT_ID"

APPS_SCRIPT_EXECUTION_HOST = "script.google.com"

COURSE_DISCOVERY_OPERATION = ClassroomOperation.COURSE_DISCOVERY.value

ALLOWED_ENVELOPE_KEYS = frozenset({"operation", "scopes", "external_mutation", "courses"})
ALLOWED_COURSE_KEYS = frozenset({"id", "name", "section", "course_state", "alternate_link"})

PROHIBITED_PAYLOAD_KEYS = frozenset(
    {
        "announcements",
        "coursework",
        "courseworkmaterials",
        "email",
        "emailaddress",
        "emails",
        "enrollmentcode",
        "enrollments",
        "gradebooksettings",
        "grades",
        "guardians",
        "invitations",
        "owner",
        "ownerid",
        "profiles",
        "roster",
        "students",
        "studentcount",
        "submissions",
        "teachers",
        "teacherfolder",
        "teachergroupemail",
        "coursegroupemail",
        "userid",
        "userids",
    }
)


def _normalize_key(key: str) -> str:
    """Compare declared payload keys ignoring case and word separators."""
    return key.replace("_", "").replace("-", "").casefold()


def _deployment_id_from_url(web_app_url: str) -> str:
    """Extract the deployment identifier encoded in an Apps Script execution URL.

    Args:
        web_app_url: HTTPS Apps Script execution URL, in either the personal
            `/macros/s/<deployment_id>/exec` or the Workspace
            `/a/macros/<domain>/s/<deployment_id>/exec` form.

    Returns:
        The deployment identifier encoded in the URL path.

    Raises:
        ValueError: If the URL is not an Apps Script web app execution URL.
    """
    path = web_app_url.removeprefix("https://").split("/", 1)[-1].split("?", 1)[0]
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) < 3 or segments[-1] != "exec" or segments[-3] != "s":
        msg = "web_app_url must be an Apps Script web app execution URL ending in '/exec'"
        raise ValueError(msg)
    return segments[-2]


class AppsScriptDeployment(BaseModel):
    """Location and identity of the dedicated Workspace Apps Script read deployment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    deployment_id: Annotated[str, Field(description="Apps Script deployment identifier")]
    web_app_url: Annotated[str, Field(description="HTTPS Apps Script web app execution URL")]

    @field_validator("deployment_id", mode="before")
    @classmethod
    def validate_deployment_id(cls, value: object) -> str:
        """Require an identifiable deployment for the audit trail."""
        if not isinstance(value, str) or not value.strip():
            msg = "deployment_id must be a non-empty string"
            raise ValueError(msg)
        return value.strip()

    @field_validator("web_app_url", mode="before")
    @classmethod
    def validate_web_app_url(cls, value: object) -> str:
        """Accept only an HTTPS Apps Script execution URL so reads cannot be redirected."""
        if not isinstance(value, str) or not value.strip():
            msg = "web_app_url must be a non-empty string"
            raise ValueError(msg)
        cleaned = value.strip()
        if not cleaned.startswith("https://"):
            msg = "web_app_url must use HTTPS"
            raise ValueError(msg)
        host = cleaned.removeprefix("https://").split("/", 1)[0].split("@")[-1].split(":")[0]
        if host.casefold() != APPS_SCRIPT_EXECUTION_HOST:
            msg = f"web_app_url host must be {APPS_SCRIPT_EXECUTION_HOST}, got '{host}'"
            raise ValueError(msg)
        _deployment_id_from_url(cleaned)
        return cleaned

    @model_validator(mode="after")
    def validate_deployment_identity(self) -> "AppsScriptDeployment":
        """Keep audit provenance honest when configuration drifts after a redeployment."""
        encoded_id = _deployment_id_from_url(self.web_app_url)
        if encoded_id != self.deployment_id:
            msg = (
                "deployment_id does not match the deployment encoded in web_app_url; "
                "update both values after redeploying the Apps Script web app"
            )
            raise ValueError(msg)
        return self


def load_apps_script_deployment(
    env: Mapping[str, str] | None = None,
) -> AppsScriptDeployment:
    """Resolve the deployment from configuration without exposing its value in errors.

    Args:
        env: Environment mapping to read; defaults to the process environment.

    Returns:
        Validated AppsScriptDeployment describing the persistent read boundary.

    Raises:
        GoogleClassroomConfigurationError: If configuration is missing or invalid.
    """
    source: Mapping[str, str] = os.environ if env is None else env

    missing = [
        name
        for name in (APPS_SCRIPT_URL_ENV_VAR, APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR)
        if not (source.get(name) or "").strip()
    ]
    if missing:
        msg = f"Missing Classroom Apps Script configuration: {', '.join(sorted(missing))}"
        raise GoogleClassroomConfigurationError(msg)

    try:
        return AppsScriptDeployment(
            deployment_id=source[APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR],
            web_app_url=source[APPS_SCRIPT_URL_ENV_VAR],
        )
    except ValueError:
        msg = (
            "Invalid Classroom Apps Script configuration in "
            f"{APPS_SCRIPT_URL_ENV_VAR} or {APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR}; "
            "the configured values are withheld from this error."
        )
        raise GoogleClassroomConfigurationError(msg) from None


class AppsScriptTransport(Protocol):
    """Minimal read-only transport contract for the Apps Script web app."""

    def fetch(self, *, url: str, operation: str) -> Mapping[str, Any]:
        """Perform one read request and return the decoded JSON envelope."""
        ...


class AppsScriptCourseDiscoveryClient:
    """Read Classroom course metadata through the persistent Apps Script boundary."""

    _REQUIRED_CATEGORIES = (ClassroomDataCategory.COURSE_METADATA,)
    _REQUIRED_SCOPES = (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)

    def __init__(
        self,
        *,
        deployment: AppsScriptDeployment,
        transport: AppsScriptTransport,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the read boundary with an injected transport and clock."""
        self._deployment = deployment
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))

    def discover_courses(
        self,
        *,
        decision: ClassroomAccessDecision,
        requested_by: str,
    ) -> ClassroomCourseDiscovery:
        """Discover accessible courses using only approved, non-personal metadata.

        Args:
            decision: Allowed decision produced by the Loop 0.6A Classroom access policy.
            requested_by: Accountable requester recorded in the discovery result.

        Returns:
            Deterministic ClassroomCourseDiscovery containing sanitized course metadata.

        Raises:
            GoogleClassroomBoundaryError: If the read is unauthorized or the payload
                exceeds the metadata-only boundary.
            GoogleClassroomReadError: If the deployment cannot be read.
            GoogleClassroomMappingError: If sanitized metadata cannot be mapped.
        """
        self._verify_decision(decision)

        try:
            envelope: object = self._transport.fetch(
                url=self._deployment.web_app_url,
                operation=COURSE_DISCOVERY_OPERATION,
            )
        except Exception as err:
            msg = (
                "Failed to read Classroom course metadata from the configured deployment "
                f"({type(err).__name__}); transport details are withheld because the "
                "execution URL is private runtime configuration."
            )
            raise GoogleClassroomReadError(msg) from None

        raw_courses = self._verify_envelope(envelope)
        courses = [self._map_course(raw_course) for raw_course in raw_courses]

        try:
            return ClassroomCourseDiscovery(
                requested_by=requested_by,
                retrieved_at=self._read_timestamp(),
                source_deployment_id=self._deployment.deployment_id,
                approved_oauth_scopes=decision.approved_oauth_scopes,
                courses=tuple(courses),
            )
        except ValueError as err:
            msg = f"Classroom course discovery result failed validation: {err}"
            raise GoogleClassroomMappingError(msg) from err

    def _verify_decision(self, decision: ClassroomAccessDecision) -> None:
        """Fail closed before contacting Google when authorization is absent or too broad."""
        if not decision.allowed:
            msg = f"Classroom course discovery is not authorized: {decision.reason}"
            raise GoogleClassroomBoundaryError(msg)
        if decision.operation.value != COURSE_DISCOVERY_OPERATION:
            msg = (
                "Classroom access decision authorizes "
                f"'{decision.operation.value}', not course discovery."
            )
            raise GoogleClassroomBoundaryError(msg)
        if decision.approved_data_categories != self._REQUIRED_CATEGORIES:
            msg = "Course discovery requires an approval limited to course_metadata."
            raise GoogleClassroomBoundaryError(msg)
        if decision.approved_oauth_scopes != self._REQUIRED_SCOPES:
            msg = "Course discovery requires exactly the classroom.courses.readonly OAuth scope."
            raise GoogleClassroomBoundaryError(msg)

    def _verify_envelope(self, envelope: object) -> tuple[Any, ...]:
        """Validate the reply envelope and return its unmapped course entries."""
        if not isinstance(envelope, Mapping):
            msg = f"Apps Script reply must be a JSON object, got {type(envelope).__name__}"
            raise GoogleClassroomReadError(msg)

        self._reject_unexpected_keys(envelope.keys(), ALLOWED_ENVELOPE_KEYS, "reply")

        missing = sorted(ALLOWED_ENVELOPE_KEYS - set(envelope.keys()))
        if missing:
            msg = f"Apps Script reply is missing required fields: {', '.join(missing)}"
            raise GoogleClassroomReadError(msg)

        if envelope["operation"] != COURSE_DISCOVERY_OPERATION:
            msg = (
                "Apps Script reply declares operation "
                f"'{envelope['operation']}', not '{COURSE_DISCOVERY_OPERATION}'."
            )
            raise GoogleClassroomBoundaryError(msg)

        if envelope["external_mutation"] is not False:
            msg = "Apps Script reply must declare external_mutation=false."
            raise GoogleClassroomBoundaryError(msg)

        scopes = envelope["scopes"]
        if not isinstance(scopes, list | tuple) or tuple(scopes) != self._REQUIRED_SCOPES:
            msg = (
                "Apps Script reply must declare exactly the classroom.courses.readonly OAuth scope."
            )
            raise GoogleClassroomBoundaryError(msg)

        courses = envelope["courses"]
        if not isinstance(courses, list | tuple):
            msg = f"Apps Script reply 'courses' must be a list, got {type(courses).__name__}"
            raise GoogleClassroomReadError(msg)

        return tuple(courses)

    def _map_course(self, raw_course: Any) -> DiscoveredClassroomCourse:
        """Map one sanitized entry, rejecting any field beyond course metadata."""
        if not isinstance(raw_course, Mapping):
            msg = f"Course entries must be JSON objects, got {type(raw_course).__name__}"
            raise GoogleClassroomReadError(msg)

        self._reject_unexpected_keys(raw_course.keys(), ALLOWED_COURSE_KEYS, "course entry")

        for key, value in raw_course.items():
            if value is not None and not isinstance(value, str):
                msg = f"Course field '{key}' must be a string or null, got {type(value).__name__}"
                raise GoogleClassroomMappingError(msg)

        try:
            return DiscoveredClassroomCourse(
                course_id=raw_course.get("id"),
                name=raw_course.get("name"),
                section=raw_course.get("section"),
                course_state=self._map_course_state(raw_course.get("course_state")),
                alternate_link=raw_course.get("alternate_link"),
            )
        except ValueError as err:
            msg = f"Failed to map Classroom course metadata: {err}"
            raise GoogleClassroomMappingError(msg) from err

    @staticmethod
    def _map_course_state(value: object) -> ClassroomCourseState:
        """Normalize the reported course state without inventing a default."""
        if not isinstance(value, str) or not value.strip():
            msg = "Course metadata must declare a course_state"
            raise GoogleClassroomMappingError(msg)
        try:
            return ClassroomCourseState(value.strip().casefold())
        except ValueError as err:
            msg = f"Unsupported Classroom course_state '{value}'"
            raise GoogleClassroomMappingError(msg) from err

    @staticmethod
    def _reject_unexpected_keys(
        keys: Any,
        allowed: frozenset[str],
        context: str,
    ) -> None:
        """Fail closed on any prohibited or unrecognized field in the payload."""
        for key in keys:
            if not isinstance(key, str):
                msg = f"Apps Script {context} contains a non-string field name"
                raise GoogleClassroomReadError(msg)
            if key in allowed:
                continue
            if _normalize_key(key) in PROHIBITED_PAYLOAD_KEYS:
                msg = (
                    f"Apps Script {context} exposes prohibited Classroom data '{key}'; "
                    "course discovery is metadata-only."
                )
                raise GoogleClassroomBoundaryError(msg)
            msg = (
                f"Apps Script {context} contains unrecognized field '{key}'; "
                "only declared course metadata is accepted."
            )
            raise GoogleClassroomBoundaryError(msg)

    def _read_timestamp(self) -> datetime:
        """Obtain a timezone-aware read timestamp for the audit trail."""
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
            msg = "Discovery clock must return a timezone-aware timestamp"
            raise GoogleClassroomMappingError(msg)
        return timestamp
