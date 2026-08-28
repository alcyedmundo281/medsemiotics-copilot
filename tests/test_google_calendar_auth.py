"""Unit tests for Google Calendar OAuth authorization helpers."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from medsemiotics.integrations.google_calendar.auth import (
    CALENDAR_READONLY_SCOPE,
    get_calendar_credentials,
)
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarAuthError,
)


class TestGoogleCalendarAuth:
    """Test suite for get_calendar_credentials."""

    def test_scope_is_readonly_only(self) -> None:
        """Verify the scope is strictly the narrowest read-only scope."""
        assert CALENDAR_READONLY_SCOPE == "https://www.googleapis.com/auth/calendar.readonly"

    def test_valid_token_file_loaded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Verify valid cached token file loads successfully."""
        token_path = tmp_path / "token.json"
        token_path.write_text('{"token": "dummy"}', encoding="utf-8")

        mock_creds = MagicMock()
        mock_creds.valid = True

        mock_from_file = MagicMock(return_value=mock_creds)
        monkeypatch.setattr(
            "medsemiotics.integrations.google_calendar.auth.Credentials.from_authorized_user_file",
            mock_from_file,
        )

        creds = get_calendar_credentials(token_path=token_path)
        assert creds == mock_creds
        mock_from_file.assert_called_once_with(
            str(token_path),
            scopes=[CALENDAR_READONLY_SCOPE],
        )

    def test_expired_token_refreshed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Verify expired token with refresh token triggers refresh and updates file."""
        token_path = tmp_path / "token.json"
        token_path.write_text('{"token": "dummy"}', encoding="utf-8")

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_val"
        mock_creds.to_json.return_value = '{"token": "refreshed"}'

        monkeypatch.setattr(
            "medsemiotics.integrations.google_calendar.auth.Credentials.from_authorized_user_file",
            MagicMock(return_value=mock_creds),
        )
        monkeypatch.setattr(
            "medsemiotics.integrations.google_calendar.auth.Request",
            MagicMock(),
        )

        creds = get_calendar_credentials(token_path=token_path)
        assert creds == mock_creds
        mock_creds.refresh.assert_called_once()
        assert token_path.read_text(encoding="utf-8") == '{"token": "refreshed"}'

    def test_missing_token_non_interactive_raises_auth_error(self, tmp_path: Path) -> None:
        """Verify non-interactive call with missing token raises GoogleCalendarAuthError."""
        missing_token = tmp_path / "non_existent_token.json"
        with pytest.raises(
            GoogleCalendarAuthError, match="No valid Google Calendar credentials found"
        ):
            get_calendar_credentials(token_path=missing_token, interactive=False)

    def test_interactive_missing_credentials_file_raises_auth_error(self, tmp_path: Path) -> None:
        """Verify interactive flow with missing client secrets raises GoogleCalendarAuthError."""
        missing_creds = tmp_path / "missing_credentials.json"
        with pytest.raises(
            GoogleCalendarAuthError, match="Interactive OAuth requires a valid client secrets file"
        ):
            get_calendar_credentials(credentials_path=missing_creds, interactive=True)


class TestGoogleCalendarWriteAuth:
    """Test suite for get_calendar_write_credentials."""

    def test_write_scope_constant(self) -> None:
        """Verify write scope constant is calendar.events."""
        from medsemiotics.integrations.google_calendar.auth import CALENDAR_EVENTS_WRITE_SCOPE

        assert CALENDAR_EVENTS_WRITE_SCOPE == "https://www.googleapis.com/auth/calendar.events"

    def test_valid_write_token_loaded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify valid write token loads successfully."""
        from medsemiotics.integrations.google_calendar.auth import (
            CALENDAR_EVENTS_WRITE_SCOPE,
            get_calendar_write_credentials,
        )

        token_path = tmp_path / "write_token.json"
        token_path.write_text('{"token": "write_val"}', encoding="utf-8")

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.scopes = [CALENDAR_EVENTS_WRITE_SCOPE]

        mock_from_file = MagicMock(return_value=mock_creds)
        monkeypatch.setattr(
            "medsemiotics.integrations.google_calendar.auth.Credentials.from_authorized_user_file",
            mock_from_file,
        )

        creds = get_calendar_write_credentials(token_path=token_path)
        assert creds == mock_creds
        mock_from_file.assert_called_once_with(
            str(token_path),
            scopes=[CALENDAR_EVENTS_WRITE_SCOPE],
        )

    def test_readonly_token_rejected_for_write(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify token with only read-only scope is rejected by get_calendar_write_credentials."""
        from medsemiotics.integrations.google_calendar.auth import (
            CALENDAR_READONLY_SCOPE,
            get_calendar_write_credentials,
        )

        token_path = tmp_path / "read_only_token.json"
        token_path.write_text('{"token": "read_val"}', encoding="utf-8")

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.scopes = [CALENDAR_READONLY_SCOPE]  # Lacks write scope!

        monkeypatch.setattr(
            "medsemiotics.integrations.google_calendar.auth.Credentials.from_authorized_user_file",
            MagicMock(return_value=mock_creds),
        )

        with pytest.raises(GoogleCalendarAuthError, match="do not contain required write scope"):
            get_calendar_write_credentials(token_path=token_path)
