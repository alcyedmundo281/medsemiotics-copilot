"""Tests for the Loop 0.8C secret-backed Calendar read credential."""

from pathlib import Path
from typing import Any

import pytest

from medsemiotics.integrations.google_calendar.auth import CALENDAR_READONLY_SCOPE
from medsemiotics.integrations.google_calendar.exceptions import GoogleCalendarAuthError
from medsemiotics.integrations.google_calendar.secret_backed_auth import (
    CALENDAR_CHANNEL_SECRETS,
    CALENDAR_CLIENT_ID_SECRET,
    CALENDAR_CLIENT_SECRET_SECRET,
    CALENDAR_REFRESH_TOKEN_SECRET,
    CalendarReadCredentials,
    build_calendar_credentials,
    load_calendar_read_credentials,
)
from medsemiotics.integrations.secrets import EnvironmentSecretSource, FileSecretSource

CLIENT_ID = "1234567890-calendar.apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-calendar-secret"
REFRESH_TOKEN = "1//0g-calendar-refresh-token"


def calendar_env(**updates: str) -> dict[str, str]:
    """Build an environment holding the complete Calendar read channel."""
    env = {
        CALENDAR_CLIENT_ID_SECRET: CLIENT_ID,
        CALENDAR_CLIENT_SECRET_SECRET: CLIENT_SECRET,
        CALENDAR_REFRESH_TOKEN_SECRET: REFRESH_TOKEN,
    }
    env.update(updates)
    return env


class TestLoadingTheCredential:
    """Verify the channel loads completely, or not at all."""

    def test_loads_the_complete_channel(self) -> None:
        credentials = load_calendar_read_credentials(EnvironmentSecretSource(calendar_env()))

        assert credentials is not None
        assert credentials.client_id == CLIENT_ID
        assert credentials.refresh_token.get_secret_value() == REFRESH_TOKEN

    def test_reports_an_unconfigured_channel_as_absent(self) -> None:
        assert load_calendar_read_credentials(EnvironmentSecretSource({})) is None

    @pytest.mark.parametrize("missing", CALENDAR_CHANNEL_SECRETS)
    def test_partial_configuration_fails_closed(self, missing: str) -> None:
        env = calendar_env()
        del env[missing]

        with pytest.raises(GoogleCalendarAuthError) as err:
            load_calendar_read_credentials(EnvironmentSecretSource(env))

        assert missing in str(err.value)
        assert CLIENT_SECRET not in str(err.value)
        assert REFRESH_TOKEN not in str(err.value)

    def test_surfaces_a_store_failure_as_a_calendar_auth_error(self, tmp_path: Path) -> None:
        (tmp_path / CALENDAR_CLIENT_ID_SECRET).write_bytes(b"\xff\xfe not utf-8")

        with pytest.raises(GoogleCalendarAuthError) as err:
            load_calendar_read_credentials(FileSecretSource(tmp_path))

        assert CALENDAR_CLIENT_ID_SECRET in str(err.value)
        assert str(tmp_path) not in str(err.value)


class TestScopeIsFixed:
    """Verify this credential can never acquire write authority."""

    def test_is_pinned_to_the_read_only_scope(self) -> None:
        credentials = load_calendar_read_credentials(EnvironmentSecretSource(calendar_env()))
        assert credentials is not None

        assert credentials.scopes == (CALENDAR_READONLY_SCOPE,)
        assert credentials.scopes[0].endswith("calendar.readonly")

    def test_rejects_an_attempt_to_declare_scopes(self) -> None:
        with pytest.raises(ValueError, match="Extra inputs"):
            CalendarReadCredentials(  # type: ignore[call-arg]
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=REFRESH_TOKEN,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )

    @pytest.mark.parametrize("client_id", ["", "   ", 12345, None])
    def test_rejects_an_unusable_client_id(self, client_id: object) -> None:
        with pytest.raises(ValueError, match="client_id"):
            CalendarReadCredentials(
                client_id=client_id,  # type: ignore[arg-type]
                client_secret=CLIENT_SECRET,  # type: ignore[arg-type]
                refresh_token=REFRESH_TOKEN,  # type: ignore[arg-type]
            )


class TestRedaction:
    """Verify the stored credential never surfaces in text."""

    def test_hides_its_secrets(self) -> None:
        credentials = load_calendar_read_credentials(EnvironmentSecretSource(calendar_env()))
        assert credentials is not None

        for rendered in (repr(credentials), str(credentials), credentials.model_dump_json()):
            assert CLIENT_SECRET not in rendered
            assert REFRESH_TOKEN not in rendered


class TestMintingCredentials:
    """Verify minting delegates to google-auth and never leaks on failure."""

    def test_builds_credentials_from_the_stored_values(self) -> None:
        credentials = load_calendar_read_credentials(EnvironmentSecretSource(calendar_env()))
        assert credentials is not None
        seen: list[CalendarReadCredentials] = []

        def factory(stored: CalendarReadCredentials) -> Any:
            seen.append(stored)
            return "minted"

        assert build_calendar_credentials(credentials, credentials_factory=factory) == "minted"
        assert seen[0].client_id == CLIENT_ID

    def test_reports_a_failed_build_without_the_values(self) -> None:
        credentials = load_calendar_read_credentials(EnvironmentSecretSource(calendar_env()))
        assert credentials is not None

        def failing_factory(_: CalendarReadCredentials) -> Any:
            msg = f"invalid_grant for {REFRESH_TOKEN}"
            raise RuntimeError(msg)

        with pytest.raises(GoogleCalendarAuthError) as err:
            build_calendar_credentials(credentials, credentials_factory=failing_factory)

        assert "RuntimeError" in str(err.value)
        assert REFRESH_TOKEN not in str(err.value)
        assert err.value.__cause__ is None
