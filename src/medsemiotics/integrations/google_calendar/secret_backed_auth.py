"""Calendar read credentials held by a secret store.

The workstation path authorizes Calendar through files on disk, which no unattended service can
use. This module reads the same kind of owner-authorized credential the Classroom caller uses,
from the same secret store, and mints Calendar access from it.

Two properties are deliberate. The scope is **fixed** to `calendar.readonly` and cannot be
configured, so this credential can never acquire write authority. And it is a *separate* credential
from the Classroom caller: one credential never accumulates both authorities.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from medsemiotics.domain.exceptions import SecretStoreError
from medsemiotics.integrations.google_calendar.auth import CALENDAR_READONLY_SCOPE
from medsemiotics.integrations.google_calendar.exceptions import GoogleCalendarAuthError
from medsemiotics.integrations.secrets import SecretSource

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

CALENDAR_CLIENT_ID_SECRET = "MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_ID"
CALENDAR_CLIENT_SECRET_SECRET = "MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_SECRET"
CALENDAR_REFRESH_TOKEN_SECRET = "MEDSEMIOTICS_CALENDAR_OAUTH_REFRESH_TOKEN"

CALENDAR_CHANNEL_SECRETS = (
    CALENDAR_CLIENT_ID_SECRET,
    CALENDAR_CLIENT_SECRET_SECRET,
    CALENDAR_REFRESH_TOKEN_SECRET,
)


class CalendarReadCredentials(BaseModel):
    """An owner-authorized credential that can only read Calendar.

    The two secret fields are `SecretStr`, so neither a log line, a traceback, nor a serialized
    model can carry their values.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: str = Field(description="OAuth client id of the operator application")
    client_secret: SecretStr = Field(description="OAuth client secret")
    refresh_token: SecretStr = Field(description="Refresh token the Calendar owner consented to")

    @field_validator("client_id", mode="before")
    @classmethod
    def validate_client_id(cls, value: object) -> str:
        """Require a non-blank client id."""
        if not isinstance(value, str) or not value.strip():
            msg = "client_id must be a non-empty string"
            raise ValueError(msg)
        return value.strip()

    @property
    def scopes(self) -> tuple[str, ...]:
        """The only scope this credential is ever minted with."""
        return (CALENDAR_READONLY_SCOPE,)


def load_calendar_read_credentials(secrets: SecretSource) -> CalendarReadCredentials | None:
    """Load the Calendar read credential from a secret store.

    A store holding none of the secrets means Calendar reading is simply not configured, and the
    caller degrades honestly. A store holding some but not all of them is a misconfiguration and
    fails closed.

    Args:
        secrets: Secret source to read from.

    Returns:
        The configured credential, or None when this channel is not configured at all.

    Raises:
        GoogleCalendarAuthError: If the channel is partially configured or invalid.
    """
    try:
        values = {name: secrets.read(name) for name in CALENDAR_CHANNEL_SECRETS}
    except SecretStoreError as err:
        raise GoogleCalendarAuthError(str(err)) from None

    if not any(values.values()):
        return None

    missing = [name for name, value in values.items() if not value]
    if missing:
        msg = (
            "The Calendar read credential is partially configured; the secret store is missing "
            f"{', '.join(sorted(missing))}. Configure all of "
            f"{', '.join(CALENDAR_CHANNEL_SECRETS)} or none of them."
        )
        raise GoogleCalendarAuthError(msg)

    try:
        return CalendarReadCredentials(
            client_id=values[CALENDAR_CLIENT_ID_SECRET],
            client_secret=SecretStr(values[CALENDAR_CLIENT_SECRET_SECRET] or ""),
            refresh_token=SecretStr(values[CALENDAR_REFRESH_TOKEN_SECRET] or ""),
        )
    except ValueError as err:
        msg = (
            "The Calendar read credential is invalid "
            f"({type(err).__name__}); the stored values are withheld."
        )
        raise GoogleCalendarAuthError(msg) from None


def _build_user_credentials(credentials: CalendarReadCredentials) -> Any:
    """Build google-auth user credentials pinned to the read-only Calendar scope."""
    from google.oauth2.credentials import Credentials

    return Credentials(
        None,
        refresh_token=credentials.refresh_token.get_secret_value(),
        token_uri=GOOGLE_TOKEN_URI,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret.get_secret_value(),
        scopes=list(credentials.scopes),
    )


def build_calendar_credentials(
    credentials: CalendarReadCredentials,
    *,
    credentials_factory: Callable[[CalendarReadCredentials], Any] = _build_user_credentials,
) -> Any:
    """Mint google-auth credentials that can only read Calendar.

    Args:
        credentials: The stored owner-authorized credential.
        credentials_factory: Builds google-auth credentials from it.

    Returns:
        Credentials usable by the Calendar reader.

    Raises:
        GoogleCalendarAuthError: If the credentials cannot be built.
    """
    try:
        return credentials_factory(credentials)
    except Exception as err:
        msg = (
            "Failed to build Calendar read credentials "
            f"({type(err).__name__}); the stored values are withheld."
        )
        raise GoogleCalendarAuthError(msg) from None
