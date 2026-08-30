"""Authenticated unattended invocation of the Apps Script course-discovery deployment.

The deployment enforces access before `doGet` runs, so an unauthenticated caller is answered with
a Google sign-in page rather than an error. This transport detects that case and every other
non-answer, and never lets the bearer token, the execution URL, or a response body reach an error
message or a log line.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from medsemiotics.integrations.google_classroom.exceptions import (
    GoogleClassroomAuthenticationError,
    GoogleClassroomConfigurationError,
    GoogleClassroomReadError,
)

DEFAULT_TIMEOUT_SECONDS = 30.0

JSON_CONTENT_TYPE = "application/json"
SIGN_IN_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
UNAUTHORIZED_STATUS_CODES = (401, 403)


@dataclass(frozen=True)
class HttpResponse:
    """Minimal HTTP response the transport needs, with no header echoing."""

    status_code: int
    content_type: str
    body: str


class HttpSender(Protocol):
    """HTTP sender contract that must not follow redirects."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        """Perform one GET request and return the response without following redirects."""
        ...

    def post(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        """Perform one POST request and return the response without following redirects."""
        ...


class BearerTokenProvider(Protocol):
    """Source of a bearer token for the dedicated Workspace identity."""

    def bearer_token(self) -> str:
        """Return a currently valid bearer token."""
        ...


class GoogleCredentialsTokenProvider:
    """Adapt any google-auth credentials object to the bearer-token contract.

    The operator decides how the identity is obtained — a Workspace user impersonated through
    domain-wide delegation, or stored user credentials for the dedicated account. This class only
    refreshes and reads the token; it never persists it.
    """

    def __init__(self, credentials: Any, request: Any) -> None:
        """Initialize with google-auth credentials and the transport request they refresh with."""
        self._credentials = credentials
        self._request = request

    def bearer_token(self) -> str:
        """Refresh the credentials when needed and return the access token.

        Returns:
            A currently valid bearer token.

        Raises:
            GoogleClassroomAuthenticationError: If no valid token can be obtained.
        """
        try:
            if not getattr(self._credentials, "valid", False):
                self._credentials.refresh(self._request)
            token = self._credentials.token
        except Exception as err:
            msg = (
                "Failed to obtain a bearer token for the Classroom deployment "
                f"({type(err).__name__}); credential details are withheld."
            )
            raise GoogleClassroomAuthenticationError(msg) from None

        if not isinstance(token, str) or not token.strip():
            msg = "The configured credentials produced no usable bearer token."
            raise GoogleClassroomAuthenticationError(msg)
        return token


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return redirects to the caller instead of following them to a sign-in page."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        """Refuse to build a redirected request."""
        return None


class UrllibHttpSender:
    """Standard-library HTTP sender that never follows redirects."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        """Perform one GET request.

        Args:
            url: Absolute HTTPS URL to read.
            headers: Request headers, including the bearer authorization.
            timeout_seconds: Socket timeout for the request.

        Returns:
            HttpResponse carrying the status, content type, and decoded body.

        Raises:
            GoogleClassroomReadError: If the request cannot be completed.
        """
        return self._send(url=url, headers=headers, body=None, timeout_seconds=timeout_seconds)

    def post(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        """Perform one POST request.

        Args:
            url: Absolute HTTPS URL to write to.
            headers: Request headers, including the bearer authorization.
            body: Encoded request body.
            timeout_seconds: Socket timeout for the request.

        Returns:
            HttpResponse carrying the status, content type, and decoded body.

        Raises:
            GoogleClassroomReadError: If the request cannot be completed.
        """
        return self._send(url=url, headers=headers, body=body, timeout_seconds=timeout_seconds)

    def _send(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        """Perform one request without following redirects."""
        opener = urllib.request.build_opener(_NoRedirectHandler)
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST" if body is not None else "GET",
        )

        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                return self._to_response(
                    status_code=response.status,
                    content_type=response.headers.get("Content-Type", ""),
                    raw_body=response.read(),
                )
        except urllib.error.HTTPError as err:
            return self._to_response(
                status_code=err.code,
                content_type=err.headers.get("Content-Type", "") if err.headers else "",
                raw_body=err.read(),
            )
        except Exception as err:
            msg = (
                "Failed to reach the configured Classroom deployment "
                f"({type(err).__name__}); the execution URL is withheld."
            )
            raise GoogleClassroomReadError(msg) from None

    @staticmethod
    def _to_response(*, status_code: int, content_type: str, raw_body: bytes) -> HttpResponse:
        """Normalize one raw response without retaining headers."""
        return HttpResponse(
            status_code=status_code,
            content_type=content_type.split(";", 1)[0].strip().casefold(),
            body=raw_body.decode("utf-8", errors="replace"),
        )


class AuthenticatedAppsScriptTransport:
    """Call the Apps Script deployment as the authorized dedicated Workspace identity."""

    def __init__(
        self,
        *,
        token_provider: BearerTokenProvider,
        sender: HttpSender | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize with a token source and an HTTP sender that does not follow redirects."""
        self._token_provider = token_provider
        self._sender = sender or UrllibHttpSender()
        self._timeout_seconds = timeout_seconds

    def fetch(self, *, url: str, operation: str) -> Mapping[str, Any]:
        """Read one operation from the deployment as an authenticated caller.

        Args:
            url: Validated Apps Script execution URL.
            operation: Operation the deployment should perform.

        Returns:
            The decoded JSON envelope, which the read boundary validates separately.

        Raises:
            GoogleClassroomAuthenticationError: If the deployment does not recognize the caller.
            GoogleClassroomConfigurationError: If the URL would carry the token in cleartext.
            GoogleClassroomReadError: If the deployment cannot be read or answers unusably.
        """
        self._require_https(url)
        token = self._token_provider.bearer_token()
        query = urllib.parse.urlencode({"operation": operation})
        separator = "&" if "?" in url else "?"

        response = self._sender.get(
            url=f"{url}{separator}{query}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": JSON_CONTENT_TYPE,
            },
            timeout_seconds=self._timeout_seconds,
        )
        return self._decode(response)

    def submit(
        self,
        *,
        url: str,
        operation: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Send one write operation to the deployment as an authenticated caller.

        Args:
            url: Validated Apps Script execution URL.
            operation: Operation the deployment should perform.
            payload: Declared write parameters; the deployment accepts nothing else.

        Returns:
            The decoded JSON envelope, which the write boundary validates separately.

        Raises:
            GoogleClassroomAuthenticationError: If the deployment does not recognize the caller.
            GoogleClassroomConfigurationError: If the URL would carry the token in cleartext.
            GoogleClassroomReadError: If the deployment cannot be reached or answers unusably.
        """
        self._require_https(url)
        token = self._token_provider.bearer_token()
        body = json.dumps({"operation": operation, **dict(payload)}).encode("utf-8")

        response = self._sender.post(
            url=url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": JSON_CONTENT_TYPE,
                "Content-Type": JSON_CONTENT_TYPE,
            },
            body=body,
            timeout_seconds=self._timeout_seconds,
        )
        return self._decode(response)

    @staticmethod
    def _require_https(url: str) -> None:
        """Refuse to send a bearer token in cleartext."""
        if not url.casefold().startswith("https://"):
            msg = "Refusing to send a bearer token to a non-HTTPS execution URL."
            raise GoogleClassroomConfigurationError(msg)

    def _decode(self, response: HttpResponse) -> Mapping[str, Any]:
        """Validate one response and decode its JSON object body."""
        self._verify_authenticated(response)

        if response.status_code != 200:
            msg = (
                f"The Classroom deployment answered HTTP {response.status_code}; "
                "the execution URL and response body are withheld."
            )
            raise GoogleClassroomReadError(msg)

        try:
            payload = json.loads(response.body)
        except ValueError:
            msg = (
                "The Classroom deployment answered with a body that is not valid JSON "
                f"(content type '{response.content_type or 'unknown'}'); the body is withheld."
            )
            raise GoogleClassroomReadError(msg) from None

        if not isinstance(payload, dict):
            msg = (
                "The Classroom deployment answered with a JSON value that is not an object "
                f"({type(payload).__name__})."
            )
            raise GoogleClassroomReadError(msg)
        return payload

    @staticmethod
    def _verify_authenticated(response: HttpResponse) -> None:
        """Detect the answers Google gives a caller it does not accept."""
        if 300 <= response.status_code < 400:
            msg = (
                f"The Classroom deployment redirected the request (HTTP {response.status_code}), "
                "which means the caller was not accepted as an authorized identity."
            )
            raise GoogleClassroomAuthenticationError(msg)

        if response.status_code in UNAUTHORIZED_STATUS_CODES:
            msg = (
                f"The Classroom deployment rejected the caller (HTTP {response.status_code}); "
                "confirm the deployment is shared with the dedicated Workspace identity."
            )
            raise GoogleClassroomAuthenticationError(msg)

        if response.content_type in SIGN_IN_CONTENT_TYPES:
            msg = (
                "The Classroom deployment answered with a sign-in page instead of JSON, which "
                "means the request reached Google unauthenticated."
            )
            raise GoogleClassroomAuthenticationError(msg)
