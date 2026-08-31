"""A minimal consumer of the read-only backend contracts.

A conversational surface — Claude Cowork, ChatGPT Work, or an operator shell — holds one thing:
the backend token. This client turns that into calls, and is deliberately small enough to read in
one sitting: it adds the headers, decodes JSON, and never lets a token reach a message, a log
line, or an exception.

The backend token travels in its own header, so a platform that authenticates callers itself —
Cloud Run with IAM, an API gateway — can keep `Authorization` for its identity token. Supply that
identity token too when the deployment requires one; the client sends both and neither is ever
printed.

It cannot write. There is no method that issues anything but a GET, because the backend serves
nothing but GETs.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from medsemiotics.api.security import BACKEND_TOKEN_HEADER
from medsemiotics.domain.exceptions import MedSemioticsError

BASE_URL_ENV_VAR = "MEDSEMIOTICS_API_BASE_URL"
IDENTITY_TOKEN_ENV_VAR = "MEDSEMIOTICS_API_IDENTITY_TOKEN"

HttpGet = Callable[[str, Mapping[str, str]], tuple[int, str]]


class BackendClientError(MedSemioticsError):
    """Raised when the backend cannot be reached or answers unusably."""


def _urllib_get(url: str, headers: Mapping[str, str]) -> tuple[int, str]:
    """Perform one GET request with the standard library."""
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")


class BackendClient:
    """Call the read-only backend with the surface's own token."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        identity_token: str | None = None,
        http_get: HttpGet = _urllib_get,
    ) -> None:
        """Initialize with the backend location and the surface's token.

        Args:
            base_url: Base URL of the deployed backend.
            token: The surface's own backend token; never a Google credential.
            identity_token: Platform identity token, when the deployment authenticates callers
                itself. It authorizes reaching the service, never reading academic state.
            http_get: Performs one GET; injected in tests.

        Raises:
            BackendClientError: If the base URL or token is unusable.
        """
        cleaned_url = (base_url or "").strip().rstrip("/")
        if not cleaned_url:
            msg = f"No backend base URL configured. Set {BASE_URL_ENV_VAR}."
            raise BackendClientError(msg)
        if not (token or "").strip():
            msg = "No backend token configured; the surface cannot authenticate."
            raise BackendClientError(msg)

        self._base_url = cleaned_url
        self._token = token.strip()
        self._identity_token = (identity_token or "").strip()
        self._http_get = http_get

    def get(self, path: str) -> Any:
        """Fetch one contract from the backend.

        Args:
            path: Contract path, such as `/v1/courses/NEURO/next-topic`.

        Returns:
            The decoded JSON payload.

        Raises:
            BackendClientError: If the backend refuses, cannot be reached, or answers
                something other than JSON. The token never appears in the message.
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            BACKEND_TOKEN_HEADER: self._token,
            "Accept": "application/json",
        }
        if self._identity_token:
            headers["Authorization"] = f"Bearer {self._identity_token}"

        try:
            status_code, body = self._http_get(url, headers)
        except Exception as err:
            msg = (
                f"Failed to reach the backend at {self._base_url} "
                f"({type(err).__name__}); the token is withheld."
            )
            raise BackendClientError(msg) from None

        if status_code == 401:
            msg = "The backend rejected the token. Rotate it in the secret store and retry."
            raise BackendClientError(msg)
        if status_code == 403:
            msg = (
                "The platform refused the request before it reached the backend. Supply a "
                f"platform identity token ({IDENTITY_TOKEN_ENV_VAR}) for a deployment that "
                "authenticates its callers."
            )
            raise BackendClientError(msg)
        if status_code == 503:
            msg = f"The backend is not fully configured: {_detail(body)}"
            raise BackendClientError(msg)
        if status_code != 200:
            msg = f"The backend answered HTTP {status_code}: {_detail(body)}"
            raise BackendClientError(msg)

        try:
            return json.loads(body)
        except ValueError:
            msg = "The backend answered with a body that is not valid JSON."
            raise BackendClientError(msg) from None


def _detail(body: str) -> str:
    """Extract the backend's explanation, falling back to a short excerpt."""
    try:
        payload = json.loads(body)
    except ValueError:
        return body.strip()[:200] or "no detail"
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
    return body.strip()[:200] or "no detail"
