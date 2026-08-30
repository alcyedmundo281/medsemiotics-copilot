"""Tests for the Loop 0.6F authenticated Apps Script invocation."""

import json
import threading
from collections.abc import Iterator, Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from medsemiotics.integrations.google_classroom import (
    AuthenticatedAppsScriptTransport,
    GoogleClassroomAuthenticationError,
    GoogleClassroomConfigurationError,
    GoogleClassroomReadError,
    GoogleCredentialsTokenProvider,
    HttpResponse,
    UrllibHttpSender,
)

WEB_APP_URL = "https://script.google.com/macros/s/AKfycb-deployment/exec"
TOKEN = "ya29.super-secret-token"
ENVELOPE = {
    "operation": "course_discovery",
    "scopes": ["https://www.googleapis.com/auth/classroom.courses.readonly"],
    "external_mutation": False,
    "courses": [],
}
SIGN_IN_PAGE = "<html><body>Sign in to continue to Apps Script</body></html>"


class FakeSender:
    """Return one canned response and record the request it was given."""

    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, str], float]] = []
        self.bodies: list[bytes] = []

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        """Record the call and return the canned response."""
        self.calls.append((url, dict(headers), timeout_seconds))
        return self.response

    def post(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        """Record the submission and return the canned response."""
        self.calls.append((url, dict(headers), timeout_seconds))
        self.bodies.append(body)
        return self.response


class StaticTokenProvider:
    """Return a fixed bearer token."""

    def bearer_token(self) -> str:
        """Return the configured token."""
        return TOKEN


def json_response(payload: object = ENVELOPE, status_code: int = 200) -> HttpResponse:
    """Build a JSON HTTP response."""
    return HttpResponse(
        status_code=status_code,
        content_type="application/json",
        body=json.dumps(payload),
    )


def make_transport(response: HttpResponse) -> tuple[AuthenticatedAppsScriptTransport, FakeSender]:
    """Build the transport over a canned response."""
    sender = FakeSender(response)
    transport = AuthenticatedAppsScriptTransport(
        token_provider=StaticTokenProvider(),
        sender=sender,
        timeout_seconds=5.0,
    )
    return transport, sender


class TestAuthenticatedInvocation:
    """Verify the transport authenticates, and asks for exactly one operation."""

    def test_sends_the_bearer_token_and_operation(self) -> None:
        transport, sender = make_transport(json_response())

        envelope = transport.fetch(url=WEB_APP_URL, operation="course_discovery")

        assert envelope == ENVELOPE
        url, headers, timeout = sender.calls[0]
        assert url == f"{WEB_APP_URL}?operation=course_discovery"
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        assert headers["Accept"] == "application/json"
        assert timeout == 5.0

    def test_appends_the_operation_to_a_url_that_already_has_a_query(self) -> None:
        transport, sender = make_transport(json_response())

        transport.fetch(url=f"{WEB_APP_URL}?v=2", operation="course_discovery")

        assert sender.calls[0][0] == f"{WEB_APP_URL}?v=2&operation=course_discovery"

    def test_refuses_to_send_a_token_over_plaintext(self) -> None:
        transport, sender = make_transport(json_response())

        with pytest.raises(GoogleClassroomConfigurationError):
            transport.fetch(
                url="http://script.google.com/macros/s/AKfycb/exec",
                operation="course_discovery",
            )

        assert sender.calls == []


class TestAuthenticatedSubmission:
    """Verify a write submission carries the token and only declared fields."""

    def test_submits_the_operation_and_payload_as_json(self) -> None:
        transport, sender = make_transport(
            HttpResponse(
                status_code=200,
                content_type="application/json",
                body=json.dumps({"operation": "coursework_draft_create"}),
            )
        )

        envelope = transport.submit(
            url=WEB_APP_URL,
            operation="coursework_draft_create",
            payload={"course_id": "770001", "title": "Taller"},
        )

        assert envelope == {"operation": "coursework_draft_create"}
        url, headers, _ = sender.calls[0]
        assert url == WEB_APP_URL
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        assert headers["Content-Type"] == "application/json"
        assert json.loads(sender.bodies[0]) == {
            "operation": "coursework_draft_create",
            "course_id": "770001",
            "title": "Taller",
        }

    def test_refuses_to_submit_over_plaintext(self) -> None:
        transport, sender = make_transport(json_response())

        with pytest.raises(GoogleClassroomConfigurationError):
            transport.submit(
                url="http://script.google.com/macros/s/AKfycb/exec",
                operation="coursework_draft_create",
                payload={},
            )

        assert sender.calls == []

    def test_reports_a_sign_in_page_on_a_submission(self) -> None:
        transport, _ = make_transport(
            HttpResponse(status_code=200, content_type="text/html", body=SIGN_IN_PAGE)
        )

        with pytest.raises(GoogleClassroomAuthenticationError):
            transport.submit(
                url=WEB_APP_URL,
                operation="coursework_draft_create",
                payload={},
            )


class TestUnauthenticatedAnswers:
    """Verify every way Google refuses a caller is reported as an authentication failure."""

    def test_detects_a_sign_in_page(self) -> None:
        transport, _ = make_transport(
            HttpResponse(status_code=200, content_type="text/html", body=SIGN_IN_PAGE)
        )

        with pytest.raises(GoogleClassroomAuthenticationError) as err:
            transport.fetch(url=WEB_APP_URL, operation="course_discovery")

        assert "sign-in page" in str(err.value)
        assert TOKEN not in str(err.value)

    def test_detects_a_redirect(self) -> None:
        transport, _ = make_transport(
            HttpResponse(status_code=302, content_type="text/html", body="")
        )

        with pytest.raises(GoogleClassroomAuthenticationError) as err:
            transport.fetch(url=WEB_APP_URL, operation="course_discovery")

        assert "redirected" in str(err.value)

    @pytest.mark.parametrize("status_code", [401, 403])
    def test_detects_a_rejected_caller(self, status_code: int) -> None:
        transport, _ = make_transport(json_response(status_code=status_code))

        with pytest.raises(GoogleClassroomAuthenticationError) as err:
            transport.fetch(url=WEB_APP_URL, operation="course_discovery")

        assert str(status_code) in str(err.value)


class TestUnusableAnswers:
    """Verify unusable answers never leak the URL, the token, or the body."""

    def test_rejects_a_non_success_status(self) -> None:
        transport, _ = make_transport(json_response(status_code=500))

        with pytest.raises(GoogleClassroomReadError) as err:
            transport.fetch(url=WEB_APP_URL, operation="course_discovery")

        assert "HTTP 500" in str(err.value)
        assert WEB_APP_URL not in str(err.value)

    def test_rejects_a_body_that_is_not_json(self) -> None:
        transport, _ = make_transport(
            HttpResponse(
                status_code=200,
                content_type="text/plain",
                body="ya29.leaked-looking-body",
            )
        )

        with pytest.raises(GoogleClassroomReadError) as err:
            transport.fetch(url=WEB_APP_URL, operation="course_discovery")

        assert "not valid JSON" in str(err.value)
        assert "ya29.leaked-looking-body" not in str(err.value)
        assert err.value.__cause__ is None

    def test_rejects_a_json_value_that_is_not_an_object(self) -> None:
        transport, _ = make_transport(json_response(payload=["course"]))

        with pytest.raises(GoogleClassroomReadError) as err:
            transport.fetch(url=WEB_APP_URL, operation="course_discovery")

        assert "not an object" in str(err.value)


class FakeCredentials:
    """Minimal stand-in for a google-auth credentials object."""

    def __init__(self, *, token: object = TOKEN, valid: bool = True, fail: bool = False) -> None:
        self.token = token
        self.valid = valid
        self.fail = fail
        self.refresh_calls = 0

    def refresh(self, request: object) -> None:  # noqa: ARG002
        """Simulate refreshing the credentials."""
        self.refresh_calls += 1
        if self.fail:
            msg = f"invalid_grant for {TOKEN}"
            raise RuntimeError(msg)
        self.valid = True


class TestGoogleCredentialsTokenProvider:
    """Verify token acquisition refreshes when needed and never leaks credential detail."""

    def test_returns_a_valid_token_without_refreshing(self) -> None:
        credentials = FakeCredentials()

        token = GoogleCredentialsTokenProvider(credentials, request=object()).bearer_token()

        assert token == TOKEN
        assert credentials.refresh_calls == 0

    def test_refreshes_expired_credentials(self) -> None:
        credentials = FakeCredentials(valid=False)

        token = GoogleCredentialsTokenProvider(credentials, request=object()).bearer_token()

        assert token == TOKEN
        assert credentials.refresh_calls == 1

    def test_reports_a_failed_refresh_without_credential_detail(self) -> None:
        credentials = FakeCredentials(valid=False, fail=True)
        provider = GoogleCredentialsTokenProvider(credentials, request=object())

        with pytest.raises(GoogleClassroomAuthenticationError) as err:
            provider.bearer_token()

        assert "RuntimeError" in str(err.value)
        assert TOKEN not in str(err.value)
        assert err.value.__cause__ is None

    @pytest.mark.parametrize("token", ["", "   ", None, 42])
    def test_rejects_an_unusable_token(self, token: object) -> None:
        provider = GoogleCredentialsTokenProvider(
            FakeCredentials(token=token),
            request=object(),
        )

        with pytest.raises(GoogleClassroomAuthenticationError):
            provider.bearer_token()


class _Handler(BaseHTTPRequestHandler):
    """Serve the answers a real deployment gives an authorized and an unauthorized caller."""

    def do_GET(self) -> None:
        """Dispatch by path."""
        if self.path.startswith("/json"):
            self._respond(200, "application/json; charset=utf-8", json.dumps(ENVELOPE))
        elif self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "https://accounts.google.com/signin")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path.startswith("/signin"):
            self._respond(200, "text/html; charset=utf-8", SIGN_IN_PAGE)
        else:
            self._respond(403, "text/plain", "forbidden")

    def do_POST(self) -> None:
        """Read the submitted body and answer like the write endpoint."""
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self._respond(200, "application/json; charset=utf-8", json.dumps(ENVELOPE))

    def _respond(self, status: int, content_type: str, body: str) -> None:
        """Write one response."""
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args: Any) -> None:  # noqa: ARG002
        """Keep the test output quiet."""
        return


@pytest.fixture
def local_server() -> Iterator[str]:
    """Serve deployment-like answers on localhost."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestUrllibHttpSender:
    """Verify the shipped sender reads answers without following redirects."""

    def test_reads_a_json_answer(self, local_server: str) -> None:
        response = UrllibHttpSender().get(
            url=f"{local_server}/json",
            headers={"Accept": "application/json"},
            timeout_seconds=5.0,
        )

        assert response.status_code == 200
        assert response.content_type == "application/json"
        assert json.loads(response.body) == ENVELOPE

    def test_returns_a_redirect_instead_of_following_it(self, local_server: str) -> None:
        response = UrllibHttpSender().get(
            url=f"{local_server}/redirect",
            headers={},
            timeout_seconds=5.0,
        )

        assert response.status_code == 302

    def test_returns_a_sign_in_page(self, local_server: str) -> None:
        response = UrllibHttpSender().get(
            url=f"{local_server}/signin",
            headers={},
            timeout_seconds=5.0,
        )

        assert response.content_type == "text/html"

    def test_returns_an_error_status_without_raising(self, local_server: str) -> None:
        response = UrllibHttpSender().get(
            url=f"{local_server}/denied",
            headers={},
            timeout_seconds=5.0,
        )

        assert response.status_code == 403

    def test_posts_a_body(self, local_server: str) -> None:
        response = UrllibHttpSender().post(
            url=f"{local_server}/json",
            headers={"Content-Type": "application/json"},
            body=b'{"operation":"coursework_draft_create"}',
            timeout_seconds=5.0,
        )

        assert response.status_code == 200
        assert json.loads(response.body) == ENVELOPE

    def test_reports_an_unreachable_deployment_without_the_url(self) -> None:
        with pytest.raises(GoogleClassroomReadError) as err:
            UrllibHttpSender().get(
                url="http://127.0.0.1:1/unreachable",
                headers={},
                timeout_seconds=1.0,
            )

        assert "127.0.0.1" not in str(err.value)
        assert err.value.__cause__ is None
