"""Tests for the Loop 0.7E owner-authorized caller and its secret store."""

from pathlib import Path
from typing import Any

import pytest

from medsemiotics.domain.exceptions import SecretStoreError
from medsemiotics.integrations.google_classroom import (
    GoogleClassroomConfigurationError,
    OwnerAuthorizedCaller,
    build_operator_token_provider,
    build_owner_authorized_token_provider,
    build_secret_source,
    describe_operator_channel,
    load_owner_authorized_caller,
)
from medsemiotics.integrations.google_classroom.operator_credentials import (
    OWNER_AUTHORIZED_CHANNEL,
    SERVICE_ACCOUNT_CHANNEL,
    SERVICE_ACCOUNT_ENV_VAR,
    SUBJECT_ENV_VAR,
    UNCONFIGURED_CHANNEL,
)
from medsemiotics.integrations.google_classroom.owner_authorized_caller import (
    CALLER_SCOPES_SECRET,
    CLIENT_ID_SECRET,
    CLIENT_SECRET_SECRET,
    DEFAULT_CALLER_SCOPES,
    REFRESH_TOKEN_SECRET,
    SECRET_DIRECTORY_ENV_VAR,
    EnvironmentSecretSource,
    FileSecretSource,
)

CLIENT_ID = "1234567890-operator.apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-super-secret-value"
REFRESH_TOKEN = "1//0g-owner-refresh-token"
KEY_FILE = "/run/secrets/classroom-operator.json"
SUBJECT = "docencia@medsemiotics.test"


def owner_env(**updates: str) -> dict[str, str]:
    """Build an environment holding the complete owner-authorized channel."""
    env = {
        CLIENT_ID_SECRET: CLIENT_ID,
        CLIENT_SECRET_SECRET: CLIENT_SECRET,
        REFRESH_TOKEN_SECRET: REFRESH_TOKEN,
    }
    env.update(updates)
    return env


class FakeCredentials:
    """Stand-in for google-auth user credentials."""

    def __init__(self, caller: OwnerAuthorizedCaller) -> None:
        self.caller = caller
        self.token = "ya29.minted-for-the-owner"
        self.valid = True


def make_owner_factory() -> tuple[Any, list[FakeCredentials]]:
    """Build a recording credentials factory for the owner channel."""
    built: list[FakeCredentials] = []

    def factory(caller: OwnerAuthorizedCaller) -> FakeCredentials:
        credentials = FakeCredentials(caller)
        built.append(credentials)
        return credentials

    return factory, built


class TestSecretSources:
    """Verify secrets are read from the store the deployment actually mounts."""

    def test_reads_environment_variables(self) -> None:
        source = EnvironmentSecretSource({CLIENT_ID_SECRET: f"  {CLIENT_ID}  ", "BLANK": "   "})

        assert source.read(CLIENT_ID_SECRET) == CLIENT_ID
        assert source.read("BLANK") is None
        assert source.read("ABSENT") is None

    def test_reads_a_mounted_secret_directory(self, tmp_path: Path) -> None:
        (tmp_path / CLIENT_ID_SECRET).write_text(f"{CLIENT_ID}\n", encoding="utf-8")
        (tmp_path / CLIENT_SECRET_SECRET).write_text("   ", encoding="utf-8")
        source = FileSecretSource(tmp_path)

        assert source.read(CLIENT_ID_SECRET) == CLIENT_ID
        assert source.read(CLIENT_SECRET_SECRET) is None
        assert source.read(REFRESH_TOKEN_SECRET) is None

    def test_mounted_files_win_over_environment_variables(self, tmp_path: Path) -> None:
        (tmp_path / REFRESH_TOKEN_SECRET).write_text("rotated-token", encoding="utf-8")
        source = build_secret_source(
            {
                SECRET_DIRECTORY_ENV_VAR: str(tmp_path),
                REFRESH_TOKEN_SECRET: "stale-token",
                CLIENT_ID_SECRET: CLIENT_ID,
            }
        )

        assert source.read(REFRESH_TOKEN_SECRET) == "rotated-token"
        assert source.read(CLIENT_ID_SECRET) == CLIENT_ID

    def test_reports_an_unreadable_secret_without_its_location(self, tmp_path: Path) -> None:
        (tmp_path / REFRESH_TOKEN_SECRET).write_bytes(b"\xff\xfe not utf-8")

        with pytest.raises(SecretStoreError) as err:
            FileSecretSource(tmp_path).read(REFRESH_TOKEN_SECRET)

        assert REFRESH_TOKEN_SECRET in str(err.value)
        assert str(tmp_path) not in str(err.value)
        assert err.value.__cause__ is None

    def test_surfaces_a_store_failure_as_a_classroom_configuration_error(
        self,
        tmp_path: Path,
    ) -> None:
        (tmp_path / CLIENT_ID_SECRET).write_bytes(b"\xff\xfe not utf-8")

        with pytest.raises(GoogleClassroomConfigurationError) as err:
            load_owner_authorized_caller(FileSecretSource(tmp_path))

        assert CLIENT_ID_SECRET in str(err.value)
        assert str(tmp_path) not in str(err.value)

    def test_falls_back_to_the_environment_without_a_directory(self) -> None:
        source = build_secret_source(owner_env())

        assert source.read(CLIENT_SECRET_SECRET) == CLIENT_SECRET


class TestOwnerAuthorizedCallerLoading:
    """Verify the channel loads completely, or not at all."""

    def test_loads_the_complete_channel(self) -> None:
        caller = load_owner_authorized_caller(EnvironmentSecretSource(owner_env()))

        assert caller is not None
        assert caller.client_id == CLIENT_ID
        assert caller.refresh_token.get_secret_value() == REFRESH_TOKEN
        assert caller.scopes == DEFAULT_CALLER_SCOPES

    def test_reports_an_unconfigured_channel_as_absent(self) -> None:
        assert load_owner_authorized_caller(EnvironmentSecretSource({})) is None

    @pytest.mark.parametrize(
        "missing",
        [CLIENT_ID_SECRET, CLIENT_SECRET_SECRET, REFRESH_TOKEN_SECRET],
    )
    def test_partial_configuration_fails_closed(self, missing: str) -> None:
        env = owner_env()
        del env[missing]

        with pytest.raises(GoogleClassroomConfigurationError) as err:
            load_owner_authorized_caller(EnvironmentSecretSource(env))

        assert missing in str(err.value)
        assert CLIENT_SECRET not in str(err.value)
        assert REFRESH_TOKEN not in str(err.value)

    def test_honours_configured_caller_scopes(self) -> None:
        caller = load_owner_authorized_caller(
            EnvironmentSecretSource(
                owner_env(**{CALLER_SCOPES_SECRET: " openid , https://example.test/scope ,"})
            )
        )

        assert caller is not None
        assert caller.scopes == ("openid", "https://example.test/scope")

    def test_wraps_an_invalid_stored_configuration(self) -> None:
        with pytest.raises(GoogleClassroomConfigurationError, match="invalid"):
            load_owner_authorized_caller(
                EnvironmentSecretSource(owner_env(**{CALLER_SCOPES_SECRET: "openid,openid"}))
            )

    def test_rejects_an_empty_scope_override(self) -> None:
        with pytest.raises(GoogleClassroomConfigurationError, match="no usable caller scope"):
            load_owner_authorized_caller(
                EnvironmentSecretSource(owner_env(**{CALLER_SCOPES_SECRET: " , , "}))
            )


class TestOwnerAuthorizedCallerModel:
    """Verify the credential model refuses inputs that could never mint a token."""

    def make(self, **updates: object) -> OwnerAuthorizedCaller:
        """Build the model directly, bypassing the secret store."""
        values: dict[str, object] = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "scopes": list(DEFAULT_CALLER_SCOPES),
        }
        values.update(updates)
        return OwnerAuthorizedCaller(**values)  # type: ignore[arg-type]

    @pytest.mark.parametrize("client_id", ["", "   ", 12345, None])
    def test_rejects_an_unusable_client_id(self, client_id: object) -> None:
        with pytest.raises(ValueError, match="client_id"):
            self.make(client_id=client_id)

    @pytest.mark.parametrize(
        "scopes",
        ["openid", [], ["   "], ["openid", "openid"]],
    )
    def test_rejects_unusable_scopes(self, scopes: object) -> None:
        with pytest.raises(ValueError, match="scopes"):
            self.make(scopes=scopes)

    def test_is_frozen(self) -> None:
        caller = self.make()

        with pytest.raises(ValueError, match="frozen"):
            caller.client_id = "changed"  # type: ignore[misc]


class TestSecretRedaction:
    """Verify stored credentials never surface in text."""

    def test_the_model_hides_its_secrets(self) -> None:
        caller = load_owner_authorized_caller(EnvironmentSecretSource(owner_env()))
        assert caller is not None

        for rendered in (repr(caller), str(caller), caller.model_dump_json()):
            assert CLIENT_SECRET not in rendered
            assert REFRESH_TOKEN not in rendered

    def test_a_failed_build_withholds_the_values(self) -> None:
        caller = load_owner_authorized_caller(EnvironmentSecretSource(owner_env()))
        assert caller is not None

        def failing_factory(_: OwnerAuthorizedCaller) -> FakeCredentials:
            msg = f"invalid_grant for {REFRESH_TOKEN}"
            raise RuntimeError(msg)

        with pytest.raises(GoogleClassroomConfigurationError) as err:
            build_owner_authorized_token_provider(
                caller,
                credentials_factory=failing_factory,
                request_factory=lambda: object(),
            )

        assert "RuntimeError" in str(err.value)
        assert REFRESH_TOKEN not in str(err.value)
        assert err.value.__cause__ is None


class TestChannelSelection:
    """Verify the owner channel is preferred and never silently bypassed."""

    def test_prefers_the_owner_channel(self) -> None:
        factory, built = make_owner_factory()

        provider = build_operator_token_provider(
            owner_env(**{SERVICE_ACCOUNT_ENV_VAR: KEY_FILE, SUBJECT_ENV_VAR: SUBJECT}),
            owner_credentials_factory=factory,
            request_factory=lambda: object(),
        )

        assert provider.bearer_token() == "ya29.minted-for-the-owner"
        assert built[0].caller.client_id == CLIENT_ID

    def test_falls_back_to_delegated_impersonation(self) -> None:
        built: list[str] = []

        class DelegatedCredentials:
            token = "ya29.delegated"
            valid = True

            def with_subject(self, subject: str) -> "DelegatedCredentials":
                built.append(subject)
                return self

        provider = build_operator_token_provider(
            {SERVICE_ACCOUNT_ENV_VAR: KEY_FILE, SUBJECT_ENV_VAR: SUBJECT},
            credentials_factory=lambda key_file, scopes: DelegatedCredentials(),  # noqa: ARG005
            request_factory=lambda: object(),
        )

        assert provider.bearer_token() == "ya29.delegated"
        assert built == [SUBJECT]

    def test_a_partial_owner_channel_never_falls_back(self) -> None:
        env = owner_env(**{SERVICE_ACCOUNT_ENV_VAR: KEY_FILE, SUBJECT_ENV_VAR: SUBJECT})
        del env[REFRESH_TOKEN_SECRET]

        with pytest.raises(GoogleClassroomConfigurationError, match="partially configured"):
            build_operator_token_provider(env, request_factory=lambda: object())

    def test_reports_both_channels_when_none_is_configured(self) -> None:
        with pytest.raises(GoogleClassroomConfigurationError) as err:
            build_operator_token_provider({}, request_factory=lambda: object())

        message = str(err.value)
        assert CLIENT_ID_SECRET in message
        assert SERVICE_ACCOUNT_ENV_VAR in message

    def test_reads_the_owner_channel_from_a_mounted_directory(self, tmp_path: Path) -> None:
        for name, value in (
            (CLIENT_ID_SECRET, CLIENT_ID),
            (CLIENT_SECRET_SECRET, CLIENT_SECRET),
            (REFRESH_TOKEN_SECRET, REFRESH_TOKEN),
        ):
            (tmp_path / name).write_text(value, encoding="utf-8")
        factory, built = make_owner_factory()

        provider = build_operator_token_provider(
            {SECRET_DIRECTORY_ENV_VAR: str(tmp_path)},
            owner_credentials_factory=factory,
            request_factory=lambda: object(),
        )

        assert provider.bearer_token() == "ya29.minted-for-the-owner"
        assert built[0].caller.refresh_token.get_secret_value() == REFRESH_TOKEN


class TestChannelDescription:
    """Verify the operator can record which channel ran, without touching a secret value."""

    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            ({}, UNCONFIGURED_CHANNEL),
            ({SERVICE_ACCOUNT_ENV_VAR: KEY_FILE}, SERVICE_ACCOUNT_CHANNEL),
        ],
    )
    def test_describes_the_selected_channel(self, env: dict[str, str], expected: str) -> None:
        assert describe_operator_channel(env) == expected

    def test_describes_the_owner_channel(self) -> None:
        assert describe_operator_channel(owner_env()) == OWNER_AUTHORIZED_CHANNEL
