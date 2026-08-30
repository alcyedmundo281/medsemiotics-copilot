"""Build the operator identity used to call the Apps Script deployment.

The repository holds no credential. This module only reads the operator's environment and secret
store, both outside Git, and hands the resulting google-auth credentials to the transport's token
provider.

Two channels are supported, in this order:

1. the **owner-authorized caller** of Loop 0.7E — the deployment owner's own credential, held by a
   secret store, which is preferred because it creates no standing domain authority;
2. **service-account impersonation** through domain-wide delegation, for deployments that already
   have that grant.

Neither is created here, and a partially configured channel fails closed rather than falling
through to the other one.
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomConfigurationError,
)
from medsemiotics.integrations.google_classroom.owner_authorized_caller import (
    DEFAULT_CALLER_SCOPES,
    OWNER_CHANNEL_SECRETS,
    OwnerAuthorizedCaller,
    SecretSource,
    build_owner_authorized_token_provider,
    build_secret_source,
    load_owner_authorized_caller,
    parse_caller_scopes,
)
from medsemiotics.integrations.google_classroom.transport import (
    GoogleCredentialsTokenProvider,
)

SERVICE_ACCOUNT_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_SERVICE_ACCOUNT_FILE"
SUBJECT_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_IMPERSONATED_SUBJECT"
CALLER_SCOPES_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES"

__all__ = [
    "CALLER_SCOPES_ENV_VAR",
    "DEFAULT_CALLER_SCOPES",
    "OWNER_AUTHORIZED_CHANNEL",
    "SERVICE_ACCOUNT_CHANNEL",
    "SERVICE_ACCOUNT_ENV_VAR",
    "SUBJECT_ENV_VAR",
    "UNCONFIGURED_CHANNEL",
    "build_operator_token_provider",
    "describe_operator_channel",
]

OWNER_AUTHORIZED_CHANNEL = "owner-authorized"
SERVICE_ACCOUNT_CHANNEL = "service-account-delegation"
UNCONFIGURED_CHANNEL = "unconfigured"


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
    secret_source: SecretSource | None = None,
    owner_credentials_factory: Callable[[OwnerAuthorizedCaller], Any] | None = None,
) -> GoogleCredentialsTokenProvider:
    """Build the bearer-token source for the caller the deployment recognizes.

    The owner-authorized channel wins whenever its secrets are present, because it creates no
    standing domain authority. Delegated service-account impersonation remains available for
    deployments already configured that way.

    Args:
        env: Environment mapping to read; defaults to the process environment.
        credentials_factory: Builds delegated service-account credentials from a key file.
        request_factory: Builds the transport request used to refresh credentials.
        secret_source: Secret source for the owner-authorized channel; defaults to the one the
            environment describes.
        owner_credentials_factory: Builds google-auth credentials from the owner-authorized caller.

    Returns:
        Token provider for the selected channel.

    Raises:
        GoogleClassroomConfigurationError: If no channel is configured, a channel is partially
            configured, or the credentials cannot be built.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    secrets = secret_source if secret_source is not None else build_secret_source(source)

    caller = load_owner_authorized_caller(secrets)
    if caller is not None:
        owner_factory_kwargs: dict[str, Any] = {"request_factory": request_factory}
        if owner_credentials_factory is not None:
            owner_factory_kwargs["credentials_factory"] = owner_credentials_factory
        return build_owner_authorized_token_provider(caller, **owner_factory_kwargs)

    key_file = (source.get(SERVICE_ACCOUNT_ENV_VAR) or "").strip()
    subject = (source.get(SUBJECT_ENV_VAR) or "").strip()
    if not key_file and not subject:
        msg = (
            "No Classroom caller is configured. Configure the owner-authorized channel "
            f"({', '.join(OWNER_CHANNEL_SECRETS)}) in the secret store, or the delegated "
            f"service-account channel ({SERVICE_ACCOUNT_ENV_VAR}, {SUBJECT_ENV_VAR})."
        )
        raise GoogleClassroomConfigurationError(msg)

    missing = [
        name
        for name, value in ((SERVICE_ACCOUNT_ENV_VAR, key_file), (SUBJECT_ENV_VAR, subject))
        if not value
    ]
    if missing:
        msg = f"Missing Classroom operator configuration: {', '.join(sorted(missing))}"
        raise GoogleClassroomConfigurationError(msg)

    scopes = parse_caller_scopes(source.get(CALLER_SCOPES_ENV_VAR))

    try:
        credentials = credentials_factory(Path(key_file), scopes).with_subject(subject)
    except Exception as err:
        msg = (
            "Failed to build Classroom operator credentials "
            f"({type(err).__name__}); the configured values are withheld."
        )
        raise GoogleClassroomConfigurationError(msg) from None

    return GoogleCredentialsTokenProvider(credentials, request=request_factory())


def describe_operator_channel(
    env: Mapping[str, str] | None = None,
    *,
    secret_source: SecretSource | None = None,
) -> str:
    """Name the caller channel the current configuration selects, without reading any secret value.

    Args:
        env: Environment mapping to read; defaults to the process environment.
        secret_source: Secret source to consult; defaults to the one the environment describes.

    Returns:
        The channel name, safe to print as verification evidence.

    Raises:
        GoogleClassroomConfigurationError: If the owner channel is partially configured.
    """
    source: Mapping[str, str] = os.environ if env is None else env
    secrets = secret_source if secret_source is not None else build_secret_source(source)

    if load_owner_authorized_caller(secrets) is not None:
        return OWNER_AUTHORIZED_CHANNEL
    if (source.get(SERVICE_ACCOUNT_ENV_VAR) or "").strip():
        return SERVICE_ACCOUNT_CHANNEL
    return UNCONFIGURED_CHANNEL
