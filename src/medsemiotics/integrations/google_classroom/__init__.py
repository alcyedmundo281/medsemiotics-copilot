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
)
from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomAuthenticationError,
    GoogleClassroomBoundaryError,
    GoogleClassroomConfigurationError,
    GoogleClassroomError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
)
from medsemiotics.integrations.google_classroom.transport import (
    AuthenticatedAppsScriptTransport,
    BearerTokenProvider,
    GoogleCredentialsTokenProvider,
    HttpResponse,
    HttpSender,
    UrllibHttpSender,
)

__all__ = [
    "ALLOWED_COURSE_KEYS",
    "ALLOWED_ENVELOPE_KEYS",
    "APPS_SCRIPT_DEPLOYMENT_ID_ENV_VAR",
    "APPS_SCRIPT_URL_ENV_VAR",
    "PROHIBITED_PAYLOAD_KEYS",
    "AppsScriptCourseDiscoveryClient",
    "AppsScriptDeployment",
    "AppsScriptTransport",
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
    "UrllibHttpSender",
    "load_apps_script_deployment",
]
