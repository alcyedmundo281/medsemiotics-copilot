"""Owner-authorized caller for the private Apps Script deployment.

Loop 0.7D left the unattended POST path unverified because no caller identity existed. This module
supplies one without creating standing domain authority: the deployment's owner authorizes it once
through a consent flow, and the resulting refresh token is held by a secret store outside Git.

A service account with domain-wide delegation would also work, and is still supported for
deployments that already have it. It is not the default: delegation lets the service account
impersonate users across the domain for the granted scopes, which is far more standing authority
than one owner-only web app call needs. The owner's own credential is scoped to what the owner
consented to and is revocable from that account alone.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from medsemiotics.domain.exceptions import SecretStoreError
from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomConfigurationError,
)
from medsemiotics.integrations.google_classroom.transport import (
    GoogleCredentialsTokenProvider,
)
from medsemiotics.integrations.secrets import (
    SECRET_DIRECTORY_ENV_VAR,
    ChainedSecretSource,
    EnvironmentSecretSource,
    FileSecretSource,
    SecretSource,
    build_secret_source,
)

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

CLIENT_ID_SECRET = "MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_ID"
CLIENT_SECRET_SECRET = "MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_SECRET"
REFRESH_TOKEN_SECRET = "MEDSEMIOTICS_CLASSROOM_OAUTH_REFRESH_TOKEN"
CALLER_SCOPES_SECRET = "MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES"

__all__ = [
    "CALLER_SCOPES_SECRET",
    "CLIENT_ID_SECRET",
    "CLIENT_SECRET_SECRET",
    "DEFAULT_CALLER_SCOPES",
    "GOOGLE_TOKEN_URI",
    "OWNER_CHANNEL_SECRETS",
    "REFRESH_TOKEN_SECRET",
    "SECRET_DIRECTORY_ENV_VAR",
    "ChainedSecretSource",
    "EnvironmentSecretSource",
    "FileSecretSource",
    "OwnerAuthorizedCaller",
    "SecretSource",
    "build_owner_authorized_token_provider",
    "build_secret_source",
    "load_owner_authorized_caller",
    "parse_caller_scopes",
]

OWNER_CHANNEL_SECRETS = (CLIENT_ID_SECRET, CLIENT_SECRET_SECRET, REFRESH_TOKEN_SECRET)

DEFAULT_CALLER_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)


class OwnerAuthorizedCaller(BaseModel):
    """Credentials the deployment's owner authorized once, for unattended calls.

    The two secret fields are `SecretStr`, so neither a log line, a traceback, nor a serialized
    model can carry their values.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: str = Field(description="OAuth client id of the operator application")
    client_secret: SecretStr = Field(description="OAuth client secret")
    refresh_token: SecretStr = Field(description="Refresh token the owner consented to")
    scopes: tuple[str, ...] = Field(description="Caller scopes the token is minted for")

    @field_validator("client_id", mode="before")
    @classmethod
    def validate_client_id(cls, value: object) -> str:
        """Require a non-blank client id."""
        if not isinstance(value, str) or not value.strip():
            msg = "client_id must be a non-empty string"
            raise ValueError(msg)
        return value.strip()

    @field_validator("scopes", mode="before")
    @classmethod
    def validate_scopes(cls, value: object) -> tuple[str, ...]:
        """Require at least one caller scope, without duplicates."""
        if not isinstance(value, list | tuple):
            msg = "scopes must be an ordered list or tuple"
            raise ValueError(msg)
        scopes = tuple(scope.strip() for scope in value if isinstance(scope, str) and scope.strip())
        if not scopes:
            msg = "scopes must contain at least one caller scope"
            raise ValueError(msg)
        if len(scopes) != len(set(scopes)):
            msg = "scopes must not contain duplicate values"
            raise ValueError(msg)
        return scopes


def parse_caller_scopes(configured: str | None) -> list[str]:
    """Parse the configured caller scopes, falling back to the documented defaults.

    Args:
        configured: Comma-separated scopes, or None when the store holds none.

    Returns:
        The scopes to request for the caller token.

    Raises:
        GoogleClassroomConfigurationError: If the configured value declares no usable scope.
    """
    if configured is None or not configured.strip():
        return list(DEFAULT_CALLER_SCOPES)
    scopes = [scope.strip() for scope in configured.split(",") if scope.strip()]
    if not scopes:
        msg = f"{CALLER_SCOPES_SECRET} declares no usable caller scope."
        raise GoogleClassroomConfigurationError(msg)
    return scopes


def load_owner_authorized_caller(secrets: SecretSource) -> OwnerAuthorizedCaller | None:
    """Load the owner-authorized caller from a secret store.

    A store holding none of the caller secrets means this channel is simply not configured, and the
    caller may fall back to another channel. A store holding some but not all of them is a
    misconfiguration and fails closed, so a half-rotated secret never silently downgrades the
    channel that is actually in use.

    Args:
        secrets: Secret source to read from.

    Returns:
        The configured caller, or None when this channel is not configured at all.

    Raises:
        GoogleClassroomConfigurationError: If the channel is partially configured or invalid.
    """
    try:
        values = {name: secrets.read(name) for name in OWNER_CHANNEL_SECRETS}
    except SecretStoreError as err:
        raise GoogleClassroomConfigurationError(str(err)) from None
    present = [name for name, value in values.items() if value]
    if not present:
        return None

    missing = [name for name, value in values.items() if not value]
    if missing:
        msg = (
            "The owner-authorized caller is partially configured; the secret store is missing "
            f"{', '.join(sorted(missing))}. Configure all of "
            f"{', '.join(OWNER_CHANNEL_SECRETS)} or none of them."
        )
        raise GoogleClassroomConfigurationError(msg)

    try:
        return OwnerAuthorizedCaller(
            client_id=values[CLIENT_ID_SECRET],
            client_secret=SecretStr(values[CLIENT_SECRET_SECRET] or ""),
            refresh_token=SecretStr(values[REFRESH_TOKEN_SECRET] or ""),
            scopes=parse_caller_scopes(secrets.read(CALLER_SCOPES_SECRET)),
        )
    except ValueError as err:
        msg = (
            "The owner-authorized caller configuration is invalid "
            f"({type(err).__name__}); the stored values are withheld."
        )
        raise GoogleClassroomConfigurationError(msg) from None


def _build_user_credentials(caller: OwnerAuthorizedCaller) -> Any:
    """Build google-auth user credentials that refresh with the owner's refresh token."""
    from google.oauth2.credentials import Credentials

    return Credentials(
        None,
        refresh_token=caller.refresh_token.get_secret_value(),
        token_uri=GOOGLE_TOKEN_URI,
        client_id=caller.client_id,
        client_secret=caller.client_secret.get_secret_value(),
        scopes=list(caller.scopes),
    )


def _default_request() -> Any:
    """Build the transport request google-auth refreshes with."""
    from google.auth.transport.requests import Request

    return Request()


def build_owner_authorized_token_provider(
    caller: OwnerAuthorizedCaller,
    *,
    credentials_factory: Callable[[OwnerAuthorizedCaller], Any] = _build_user_credentials,
    request_factory: Callable[[], Any] = _default_request,
) -> GoogleCredentialsTokenProvider:
    """Build the bearer-token source for the deployment owner's own identity.

    Args:
        caller: Credentials the owner authorized once.
        credentials_factory: Builds google-auth credentials from the caller.
        request_factory: Builds the transport request used to refresh them.

    Returns:
        Token provider that mints access tokens as the deployment owner.

    Raises:
        GoogleClassroomConfigurationError: If the credentials cannot be built.
    """
    try:
        credentials = credentials_factory(caller)
    except Exception as err:
        msg = (
            "Failed to build owner-authorized caller credentials "
            f"({type(err).__name__}); the stored values are withheld."
        )
        raise GoogleClassroomConfigurationError(msg) from None

    return GoogleCredentialsTokenProvider(credentials, request=request_factory())
