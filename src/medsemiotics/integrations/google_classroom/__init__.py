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
    GoogleClassroomBoundaryError,
    GoogleClassroomConfigurationError,
    GoogleClassroomError,
    GoogleClassroomMappingError,
    GoogleClassroomReadError,
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
    "GoogleClassroomBoundaryError",
    "GoogleClassroomConfigurationError",
    "GoogleClassroomError",
    "GoogleClassroomMappingError",
    "GoogleClassroomReadError",
    "load_apps_script_deployment",
]
