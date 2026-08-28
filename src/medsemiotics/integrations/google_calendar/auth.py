"""OAuth 2.0 user authorization for Google Calendar read and write access."""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarAuthError,
)

CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_EVENTS_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def get_calendar_credentials(
    *,
    credentials_path: Path | str | None = None,
    token_path: Path | str | None = None,
    interactive: bool = False,
) -> Credentials:
    """Load or refresh OAuth 2.0 user credentials for Google Calendar readonly access.

    Args:
        credentials_path: Path to OAuth client_secrets.json (or reads GOOGLE_CALENDAR_CREDENTIALS_FILE).
        token_path: Path to saved token.json cache (or reads GOOGLE_CALENDAR_TOKEN_FILE).
        interactive: If True and token is absent/invalid, launch local browser auth flow.

    Returns:
        Valid google.oauth2.credentials.Credentials instance with readonly scope.

    Raises:
        GoogleCalendarAuthError: If credentials cannot be loaded, refreshed, or authorized.
    """
    token_file = (
        Path(token_path)
        if token_path
        else Path(os.environ["GOOGLE_CALENDAR_TOKEN_FILE"])
        if os.environ.get("GOOGLE_CALENDAR_TOKEN_FILE")
        else None
    )

    creds_file = (
        Path(credentials_path)
        if credentials_path
        else Path(os.environ["GOOGLE_CALENDAR_CREDENTIALS_FILE"])
        if os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_FILE")
        else None
    )

    creds: Credentials | None = None

    if token_file and token_file.is_file():
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_file),
                scopes=[CALENDAR_READONLY_SCOPE],
            )
        except Exception as err:
            msg = f"Failed to load cached credentials from {token_file}: {err}"
            raise GoogleCalendarAuthError(msg) from err

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            if token_file:
                token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as err:
            msg = f"Failed to refresh expired OAuth token: {err}"
            raise GoogleCalendarAuthError(msg) from err

    if interactive:
        if not creds_file or not creds_file.is_file():
            msg = (
                f"Interactive OAuth requires a valid client secrets file at {creds_file}. "
                "Configure GOOGLE_CALENDAR_CREDENTIALS_FILE or pass credentials_path."
            )
            raise GoogleCalendarAuthError(msg)

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_file),
                scopes=[CALENDAR_READONLY_SCOPE],
            )
            creds = flow.run_local_server(port=0)
            if token_file:
                token_file.parent.mkdir(parents=True, exist_ok=True)
                token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as err:
            msg = f"Interactive OAuth authorization flow failed: {err}"
            raise GoogleCalendarAuthError(msg) from err

    msg = (
        "No valid Google Calendar credentials found. "
        "Provide a valid token file or invoke authorization with interactive=True."
    )
    raise GoogleCalendarAuthError(msg)


def get_calendar_write_credentials(
    *,
    credentials_path: Path | str | None = None,
    token_path: Path | str | None = None,
    interactive: bool = False,
) -> Credentials:
    """Load or refresh OAuth 2.0 user credentials explicitly for Google Calendar event write access.

    Args:
        credentials_path: Path to OAuth client_secrets.json (or reads GOOGLE_CALENDAR_CREDENTIALS_FILE).
        token_path: Path to saved token.json cache (or reads GOOGLE_CALENDAR_TOKEN_FILE).
        interactive: If True and write token is absent/invalid, launch local browser auth flow.

    Returns:
        Valid google.oauth2.credentials.Credentials instance with calendar.events write scope.

    Raises:
        GoogleCalendarAuthError: If write credentials cannot be loaded, refreshed, or authorized.
    """
    token_file = (
        Path(token_path)
        if token_path
        else Path(os.environ["GOOGLE_CALENDAR_TOKEN_FILE"])
        if os.environ.get("GOOGLE_CALENDAR_TOKEN_FILE")
        else None
    )

    creds_file = (
        Path(credentials_path)
        if credentials_path
        else Path(os.environ["GOOGLE_CALENDAR_CREDENTIALS_FILE"])
        if os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_FILE")
        else None
    )

    creds: Credentials | None = None

    if token_file and token_file.is_file():
        try:
            creds = Credentials.from_authorized_user_file(
                str(token_file),
                scopes=[CALENDAR_EVENTS_WRITE_SCOPE],
            )
        except Exception as err:
            msg = f"Failed to load cached write credentials from {token_file}: {err}"
            raise GoogleCalendarAuthError(msg) from err

        # Verify that granted scopes include write scope
        if creds.scopes and CALENDAR_EVENTS_WRITE_SCOPE not in creds.scopes:
            msg = (
                f"Cached credentials in {token_file} do not contain required write scope "
                f"'{CALENDAR_EVENTS_WRITE_SCOPE}'. Granted scopes: {creds.scopes}."
            )
            raise GoogleCalendarAuthError(msg)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            if token_file:
                token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as err:
            msg = f"Failed to refresh expired OAuth write token: {err}"
            raise GoogleCalendarAuthError(msg) from err

    if interactive:
        if not creds_file or not creds_file.is_file():
            msg = (
                f"Interactive OAuth requires a valid client secrets file at {creds_file}. "
                "Configure GOOGLE_CALENDAR_CREDENTIALS_FILE or pass credentials_path."
            )
            raise GoogleCalendarAuthError(msg)

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_file),
                scopes=[CALENDAR_EVENTS_WRITE_SCOPE],
            )
            creds = flow.run_local_server(port=0)
            if token_file:
                token_file.parent.mkdir(parents=True, exist_ok=True)
                token_file.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as err:
            msg = f"Interactive OAuth write authorization flow failed: {err}"
            raise GoogleCalendarAuthError(msg) from err

    msg = (
        "No valid Google Calendar write credentials found. "
        "Provide a valid write token file or invoke authorization with interactive=True."
    )
    raise GoogleCalendarAuthError(msg)
