"""Access control for the read-only MedSemiotics backend.

The mobile and conversational surfaces consume these contracts with a token of their own; they
never receive a Google credential. A backend with no token configured refuses to serve academic
state at all, so a misconfigured deployment cannot silently become a public one.
"""

import secrets

from fastapi import Header, HTTPException, Request, status

BEARER_PREFIX = "Bearer "


def require_backend_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Authorize one request against the configured backend token.

    Args:
        request: Incoming request, carrying the configured settings in application state.
        authorization: Value of the Authorization header, if present.

    Raises:
        HTTPException: 503 when the backend has no token configured, 401 when the caller presents
            no valid token.
    """
    expected = getattr(request.app.state, "api_token", None)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This backend has no access token configured, so it will not serve academic "
                "state. Configure MEDSEMIOTICS_API_TOKEN in the secret store."
            ),
        )

    presented = ""
    if authorization and authorization.startswith(BEARER_PREFIX):
        presented = authorization[len(BEARER_PREFIX) :].strip()

    if not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
