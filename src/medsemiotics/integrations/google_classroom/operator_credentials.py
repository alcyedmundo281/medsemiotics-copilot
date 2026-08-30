"""Build the operator identity used to call the Apps Script deployment.

The repository holds no credential. This module only reads the operator's environment, which lives
outside Git, and hands the resulting google-auth credentials to the transport's token provider.
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomConfigurationError,
)
from medsemiotics.integrations.google_classroom.transport import (
    GoogleCredentialsTokenProvider,
)

SERVICE_ACCOUNT_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_SERVICE_ACCOUNT_FILE"
SUBJECT_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_IMPERSONATED_SUBJECT"
CALLER_SCOPES_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES"

DEFAULT_CALLER_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)


def _load_service_account_credentials(key_file: Path, scopes: list[str]) -> Any:
    """Load service account credentials from a key file."""
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_file(str(key_file), scopes=scopes)


def _default_request() -> Any:
    """Build the transport request google-auth refreshes with."""
    from google.auth.transport.requests import Request

    return Request()


def build_operator_token_provider(
    env: Mapping[str, str] | None = None,
    *,
    credentials_factory: Callable[[Path, list[str]], Any] = _load_service_account_credentials,
    request_factory: Callable[[], Any] = _default_request,
) -> GoogleCredentialsTokenProvider:
    """Build the bearer-token source for the dedicated Workspace identity.

    Args:
        env: Environment mapping to read; defaults to the process environment.
        credentials_factory: Builds google-auth credentials from a key file and scopes.
        request_factory: Builds the transport request used to refresh credentials.

    Returns:
        Token provider wrapping impersonated credentials for the deployment's owner.

    Raises:
        GoogleClassroomConfigurationError: If the operator environment is incomplete or the
            credentials cannot be built.
    """
    source: Mapping[str, str] = os.environ if env is None else env

    key_file = (source.get(SERVICE_ACCOUNT_ENV_VAR) or "").strip()
    subject = (source.get(SUBJECT_ENV_VAR) or "").strip()
    missing = [
        name
        for name, value in ((SERVICE_ACCOUNT_ENV_VAR, key_file), (SUBJECT_ENV_VAR, subject))
        if not value
    ]
    if missing:
        msg = f"Missing Classroom operator configuration: {', '.join(sorted(missing))}"
        raise GoogleClassroomConfigurationError(msg)

    configured_scopes = (source.get(CALLER_SCOPES_ENV_VAR) or "").strip()
    scopes = (
        [scope.strip() for scope in configured_scopes.split(",") if scope.strip()]
        if configured_scopes
        else list(DEFAULT_CALLER_SCOPES)
    )
    if not scopes:
        msg = f"{CALLER_SCOPES_ENV_VAR} declares no usable caller scope."
        raise GoogleClassroomConfigurationError(msg)

    try:
        credentials = credentials_factory(Path(key_file), scopes).with_subject(subject)
    except Exception as err:
        msg = (
            "Failed to build Classroom operator credentials "
            f"({type(err).__name__}); the configured values are withheld."
        )
        raise GoogleClassroomConfigurationError(msg) from None

    return GoogleCredentialsTokenProvider(credentials, request=request_factory())
