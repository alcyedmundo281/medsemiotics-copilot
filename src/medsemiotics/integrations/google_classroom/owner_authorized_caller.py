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

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomConfigurationError,
)
from medsemiotics.integrations.google_classroom.transport import (
    GoogleCredentialsTokenProvider,
)

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

CLIENT_ID_SECRET = "MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_ID"
CLIENT_SECRET_SECRET = "MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_SECRET"
REFRESH_TOKEN_SECRET = "MEDSEMIOTICS_CLASSROOM_OAUTH_REFRESH_TOKEN"
CALLER_SCOPES_SECRET = "MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES"
SECRET_DIRECTORY_ENV_VAR = "MEDSEMIOTICS_CLASSROOM_SECRET_DIR"

OWNER_CHANNEL_SECRETS = (CLIENT_ID_SECRET, CLIENT_SECRET_SECRET, REFRESH_TOKEN_SECRET)

DEFAULT_CALLER_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)


class SecretSource(Protocol):
    """Read one named secret from a store that lives outside the repository."""

    def read(self, name: str) -> str | None:
        """Return the secret's value, or None when this source does not hold it."""
        ...


class EnvironmentSecretSource:
    """Read secrets from environment variables.

    Cloud Run and Kubernetes both expose a secret manager version as an environment variable, so
    this covers the managed case as well as local operator shells.
    """

    def __init__(self, env: Mapping[str, str]) -> None:
        """Initialize with the environment mapping to read."""
        self._env = env

    def read(self, name: str) -> str | None:
        """Return the variable's value, treating blank as absent."""
        value = (self._env.get(name) or "").strip()
        return value or None


class FileSecretSource:
    """Read secrets from a mounted directory, one file per secret.

    This is the shape a secret manager takes when its versions are mounted as a volume: the file
    name is the secret name and the file body is the value. Nothing is cached, so a rotated secret
    is picked up on the next read.
    """

    def __init__(self, directory: Path) -> None:
        """Initialize with the directory the secret store mounts."""
        self._directory = directory

    def read(self, name: str) -> str | None:
        """Return the file's contents, treating a missing or blank file as absent.

        Raises:
            GoogleClassroomConfigurationError: If the file exists but cannot be read or decoded.
        """
        path = self._directory / name
        if not path.is_file():
            return None
        try:
            value = path.read_text(encoding="utf-8").strip()
        except (OSError, ValueError) as err:
            msg = (
                f"Failed to read the mounted secret '{name}' "
                f"({type(err).__name__}); its location and value are withheld."
            )
            raise GoogleClassroomConfigurationError(msg) from None
        return value or None


class ChainedSecretSource:
    """Read from several sources in order, taking the first that holds the secret."""

    def __init__(self, *sources: SecretSource) -> None:
        """Initialize with the sources to consult in precedence order."""
        self._sources = sources

    def read(self, name: str) -> str | None:
        """Return the first non-empty value any source holds."""
        for source in self._sources:
            value = source.read(name)
            if value:
                return value
        return None


def build_secret_source(env: Mapping[str, str]) -> SecretSource:
    """Build the secret source described by the environment.

    A mounted secret directory takes precedence over environment variables, so a deployment can
    rotate a secret in its store without redeploying to change a variable.

    Args:
        env: Environment mapping, which may point at a mounted secret directory.

    Returns:
        The secret source to read caller credentials from.
    """
    directory = (env.get(SECRET_DIRECTORY_ENV_VAR) or "").strip()
    environment_source = EnvironmentSecretSource(env)
    if not directory:
        return environment_source
    return ChainedSecretSource(FileSecretSource(Path(directory)), environment_source)


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
    values = {name: secrets.read(name) for name in OWNER_CHANNEL_SECRETS}
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
