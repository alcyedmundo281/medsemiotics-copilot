"""Google Classroom integration package (metadata-only read boundary)."""

from medsemiotics.integrations.google_classroom.apps_script import (
    ALLOWED_COURSE_KEYS,
    ALLOWED_ENVELOPE_KEYS,
    APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR,
    APPS_SCRIPT_URL_ENV_VAR,
    PROHIBITED_PAYLOAD_KEYS,
    AppsScriptCourseDiscoveryClient,
    AppsScriptDeployment,
    AppsScriptTransport,
    load_apps_script_deployment,
    reject_unexpected_keys,
)
from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomAuthenticationError,
    GoogleClassroomBoundaryError,
    GoogleClassroomConfigurationError,
    GoogleClassroomError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
)
from medsemiotics.integrations.google_classroom.material_writer import (
    ALLOWED_MATERIAL_ENVELOPE_KEYS,
    ALLOWED_MATERIAL_REPLY_KEYS,
    AppsScriptCourseworkMaterialWriter,
)
from medsemiotics.integrations.google_classroom.operator_credentials import (
    build_operator_token_provider,
    describe_operator_channel,
)
from medsemiotics.integrations.google_classroom.owner_authorized_caller import (
    OwnerAuthorizedCaller,
    build_owner_authorized_token_provider,
    build_secret_source,
    load_owner_authorized_caller,
)
from medsemiotics.integrations.google_classroom.transport import (
    AuthenticatedAppsScriptTransport,
    BearerTokenProvider,
    GoogleCredentialsTokenProvider,
    HttpResponse,
    HttpSender,
    UrllibHttpSender,
)
from medsemiotics.integrations.google_classroom.writer import (
    ALLOWED_COURSEWORK_KEYS,
    ALLOWED_WRITE_ENVELOPE_KEYS,
    AppsScriptCourseworkWriter,
    AppsScriptWriteTransport,
)

__all__ = [
    "ALLOWED_COURSEWORK_KEYS",
    "ALLOWED_COURSE_KEYS",
    "ALLOWED_ENVELOPE_KEYS",
    "ALLOWED_MATERIAL_ENVELOPE_KEYS",
    "ALLOWED_MATERIAL_REPLY_KEYS",
    "ALLOWED_WRITE_ENVELOPE_KEYS",
    "APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR",
    "APPS_SCRIPT_URL_ENV_VAR",
    "PROHIBITED_PAYLOAD_KEYS",
    "AppsScriptCourseDiscoveryClient",
    "AppsScriptCourseworkMaterialWriter",
    "AppsScriptCourseworkWriter",
    "AppsScriptDeployment",
    "AppsScriptTransport",
    "AppsScriptWriteTransport",
    "AuthenticatedAppsScriptTransport",
    "BearerTokenProvider",
    "GoogleClassroomAuthenticationError",
    "GoogleClassroomBoundaryError",
    "GoogleClassroomConfigurationError",
    "GoogleClassroomError",
    "GoogleClassroomMappingError",
    "GoogleClassroomReadError",
    "GoogleCredentialsTokenProvider",
    "HttpResponse",
    "HttpSender",
    "OwnerAuthorizedCaller",
    "UrllibHttpSender",
    "build_operator_token_provider",
    "build_owner_authorized_token_provider",
    "build_secret_source",
    "describe_operator_channel",
    "load_apps_script_deployment",
    "load_owner_authorized_caller",
    "reject_unexpected_keys",
]
