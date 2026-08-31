"""Tests for the Loop 0.8E consumer of the read-only backend contracts."""

import json
from collections.abc import Mapping

import pytest

from medsemiotics.api.client import (
    BASE_URL_ENV_VAR,
    IDENTITY_TOKEN_ENV_VAR,
    BackendClient,
    BackendClientError,
)
from medsemiotics.api.security import BACKEND_TOKEN_HEADER

BASE_URL = "https://medsemiotics-backend.example.run.app"
TOKEN = "surface-backend-token"


class RecordingHttp:
    """Record one GET and return a canned response."""

    def __init__(self, status_code: int = 200, body: str = "{}") -> None:
        self.status_code = status_code
        self.body = body
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> tuple[int, str]:
        """Record the request and return the canned response."""
        self.calls.append((url, dict(headers)))
        return self.status_code, self.body


def make_client(http: RecordingHttp, **updates: object) -> BackendClient:
    """Build a client over a recording transport."""
    values: dict[str, object] = {"base_url": BASE_URL, "token": TOKEN}
    values.update(updates)
    return BackendClient(http_get=http, **values)  # type: ignore[arg-type]


class TestConfiguration:
    """Verify the surface cannot be built without what it needs."""

    @pytest.mark.parametrize("base_url", ["", "   "])
    def test_requires_a_base_url(self, base_url: str) -> None:
        with pytest.raises(BackendClientError) as err:
            make_client(RecordingHttp(), base_url=base_url)

        assert BASE_URL_ENV_VAR in str(err.value)

    @pytest.mark.parametrize("token", ["", "   "])
    def test_requires_a_token(self, token: str) -> None:
        with pytest.raises(BackendClientError, match="cannot authenticate"):
            make_client(RecordingHttp(), token=token)


class TestRequests:
    """Verify the surface authenticates and asks only for what it was told to."""

    def test_sends_the_backend_token_in_its_own_header(self) -> None:
        http = RecordingHttp(body=json.dumps({"topic_id": "neuro-intro"}))

        payload = make_client(http).get("/v1/courses/NEURO/next-topic")

        assert payload == {"topic_id": "neuro-intro"}
        url, headers = http.calls[0]
        assert url == f"{BASE_URL}/v1/courses/NEURO/next-topic"
        assert headers[BACKEND_TOKEN_HEADER] == TOKEN
        assert "Authorization" not in headers

    def test_sends_both_tokens_behind_a_platform_that_authenticates_callers(self) -> None:
        http = RecordingHttp()

        make_client(http, identity_token="google-identity-token").get("/v1/semester")

        headers = http.calls[0][1]
        assert headers[BACKEND_TOKEN_HEADER] == TOKEN
        assert headers["Authorization"] == "Bearer google-identity-token"

    def test_explains_a_platform_refusal(self) -> None:
        http = RecordingHttp(status_code=403, body="Forbidden")

        with pytest.raises(BackendClientError) as err:
            make_client(http).get("/v1/semester")

        assert IDENTITY_TOKEN_ENV_VAR in str(err.value)
        assert TOKEN not in str(err.value)

    def test_normalizes_slashes(self) -> None:
        http = RecordingHttp()

        make_client(http, base_url=f"{BASE_URL}/").get("v1/semester")

        assert http.calls[0][0] == f"{BASE_URL}/v1/semester"


class TestFailures:
    """Verify every failure explains itself without echoing the token."""

    def test_explains_a_rejected_token(self) -> None:
        http = RecordingHttp(status_code=401, body='{"detail":"A valid bearer token is required."}')

        with pytest.raises(BackendClientError) as err:
            make_client(http).get("/v1/semester")

        assert "Rotate it" in str(err.value)
        assert TOKEN not in str(err.value)

    def test_relays_an_unconfigured_backend(self) -> None:
        http = RecordingHttp(
            status_code=503,
            body='{"detail":"Configure MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_ID."}',
        )

        with pytest.raises(BackendClientError) as err:
            make_client(http).get("/v1/courses/NEURO/brief")

        assert "MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_ID" in str(err.value)

    @pytest.mark.parametrize(
        ("status_code", "body"),
        [(404, '{"detail":"No tracked schedule."}'), (500, "internal error"), (302, "")],
    )
    def test_explains_any_other_status(self, status_code: int, body: str) -> None:
        http = RecordingHttp(status_code=status_code, body=body)

        with pytest.raises(BackendClientError) as err:
            make_client(http).get("/v1/semester")

        assert str(status_code) in str(err.value)
        assert TOKEN not in str(err.value)

    def test_falls_back_when_the_detail_is_not_text(self) -> None:
        http = RecordingHttp(status_code=500, body='{"detail":{"nested":true}}')

        with pytest.raises(BackendClientError) as err:
            make_client(http).get("/v1/semester")

        assert "nested" in str(err.value)

    def test_rejects_a_body_that_is_not_json(self) -> None:
        http = RecordingHttp(body="<html>gateway</html>")

        with pytest.raises(BackendClientError, match="not valid JSON"):
            make_client(http).get("/v1/semester")

    def test_reports_an_unreachable_backend_without_the_token(self) -> None:
        def failing(url: str, headers: Mapping[str, str]) -> tuple[int, str]:  # noqa: ARG001
            msg = f"connection refused while sending {TOKEN}"
            raise ConnectionError(msg)

        with pytest.raises(BackendClientError) as err:
            BackendClient(base_url=BASE_URL, token=TOKEN, http_get=failing).get("/v1/semester")

        assert TOKEN not in str(err.value)
        assert "ConnectionError" in str(err.value)
        assert err.value.__cause__ is None
