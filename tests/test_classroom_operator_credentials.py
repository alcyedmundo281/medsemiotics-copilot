"""Tests for the Loop 0.6F operator identity used to call the deployment."""

from pathlib import Path
from typing import Any

import pytest

from medsemiotics.integrations.google_classroom import (
    GoogleClassroomConfigurationError,
    build_operator_token_provider,
)
from medsemiotics.integrations.google_classroom.operator_credentials import (
    CALLER_SCOPES_ENV_VAR,
    DEFAULT_CALLER_SCOPES,
    SERVICE_ACCOUNT_ENV_VAR,
    SUBJECT_ENV_VAR,
)

KEY_FILE = "/run/secrets/classroom-operator.json"
SUBJECT = "docencia@medsemiotics.test"


class FakeCredentials:
    """Record impersonation and expose a token."""

    def __init__(self, key_file: Path, scopes: list[str]) -> None:
        self.key_file = key_file
        self.scopes = scopes
        self.subject: str | None = None
        self.token = "ya29.token"
        self.valid = True

    def with_subject(self, subject: str) -> "FakeCredentials":
        """Return credentials impersonating the given subject."""
        self.subject = subject
        return self


def make_env(**updates: str) -> dict[str, str]:
    """Build a complete operator environment."""
    env = {
        SERVICE_ACCOUNT_ENV_VAR: KEY_FILE,
        SUBJECT_ENV_VAR: SUBJECT,
    }
    env.update(updates)
    return env


def make_factory() -> tuple[Any, list[FakeCredentials]]:
    """Build a recording credentials factory."""
    built: list[FakeCredentials] = []

    def factory(key_file: Path, scopes: list[str]) -> FakeCredentials:
        credentials = FakeCredentials(key_file, scopes)
        built.append(credentials)
        return credentials

    return factory, built


class TestOperatorTokenProvider:
    """Verify the operator identity is impersonated with the declared scopes."""

    def test_impersonates_the_dedicated_workspace_user(self) -> None:
        factory, built = make_factory()

        provider = build_operator_token_provider(
            make_env(),
            credentials_factory=factory,
            request_factory=lambda: object(),
        )

        assert provider.bearer_token() == "ya29.token"
        assert built[0].key_file == Path(KEY_FILE)
        assert built[0].subject == SUBJECT
        assert built[0].scopes == list(DEFAULT_CALLER_SCOPES)

    def test_honours_configured_caller_scopes(self) -> None:
        factory, built = make_factory()

        build_operator_token_provider(
            make_env(**{CALLER_SCOPES_ENV_VAR: " openid , https://example.test/scope ,"}),
            credentials_factory=factory,
            request_factory=lambda: object(),
        )

        assert built[0].scopes == ["openid", "https://example.test/scope"]

    @pytest.mark.parametrize("missing", [SERVICE_ACCOUNT_ENV_VAR, SUBJECT_ENV_VAR])
    def test_reports_missing_configuration_without_leaking_values(self, missing: str) -> None:
        factory, _ = make_factory()
        env = make_env()
        env[missing] = "   "

        with pytest.raises(GoogleClassroomConfigurationError) as err:
            build_operator_token_provider(
                env,
                credentials_factory=factory,
                request_factory=lambda: object(),
            )

        assert missing in str(err.value)
        assert KEY_FILE not in str(err.value)
        assert SUBJECT not in str(err.value)

    def test_rejects_an_empty_scope_override(self) -> None:
        factory, _ = make_factory()

        with pytest.raises(GoogleClassroomConfigurationError, match="no usable caller scope"):
            build_operator_token_provider(
                make_env(**{CALLER_SCOPES_ENV_VAR: " , , "}),
                credentials_factory=factory,
                request_factory=lambda: object(),
            )

    def test_reports_a_failed_build_without_credential_detail(self) -> None:
        def failing_factory(key_file: Path, scopes: list[str]) -> FakeCredentials:  # noqa: ARG001
            msg = f"cannot read {KEY_FILE}"
            raise OSError(msg)

        with pytest.raises(GoogleClassroomConfigurationError) as err:
            build_operator_token_provider(
                make_env(),
                credentials_factory=failing_factory,
                request_factory=lambda: object(),
            )

        assert "OSError" in str(err.value)
        assert KEY_FILE not in str(err.value)
        assert err.value.__cause__ is None
