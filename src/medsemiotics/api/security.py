"""Access control for the read-only MedSemiotics backend.

The mobile and conversational surfaces consume these contracts with a token of their own; they
never receive a Google credential. A backend with no token configured refuses to serve academic
state at all, so a misconfigured deployment cannot silently become a public one.

The backend token is accepted in either of two headers, because a platform may already own one of
them:

- `X-MedSemiotics-Token`, the dedicated header. Behind a platform that authenticates callers
  itself — Cloud Run with IAM, an API gateway — `Authorization` carries that platform's identity
  token, and the backend token needs a header of its own.
- `Authorization: Bearer`, for a deployment where nothing else claims that header.

The dedicated header wins when both are present, so a platform identity token in `Authorization`
never has to be mistaken for a backend token. The two checks are independent layers, not
alternatives: the platform decides who may reach the service, and the backend token decides who may
read academic state.
"""

import secrets

from fastapi import Header, HTTPException, Request, status

BEARER_PREFIX = "Bearer "
BACKEND_TOKEN_HEADER = "X-MedSemiotics-Token"


def require_backend_token(
    request: Request,
    authorization: str | None = Header(default=None),
    x_medsemiotics_token: str | None = Header(default=None),
) -> None:
    """Authorize one request against the configured backend token.

    Args:
        request: Incoming request, carrying the configured settings in application state. An
            application that has not been configured yet is configured here, because this check
            runs before any endpoint body.
        authorization: Value of the Authorization header, if present.
        x_medsemiotics_token: Value of the dedicated backend-token header, if present.

    Raises:
        HTTPException: 503 when the backend has no token configured, 401 when the caller presents
            no valid token.
    """
    if not getattr(request.app.state, "configured", False):
        from medsemiotics.api.app import ensure_configured

        ensure_configured()

    expected = getattr(request.app.state, "api_token", None)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This backend has no access token configured, so it will not serve academic "
                "state. Configure MEDSEMIOTICS_API_TOKEN in the secret store."
            ),
        )

    presented = (x_medsemiotics_token or "").strip()
    if not presented and authorization and authorization.startswith(BEARER_PREFIX):
        presented = authorization[len(BEARER_PREFIX) :].strip()

    if not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "A valid backend token is required, in the "
                f"{BACKEND_TOKEN_HEADER} header or as an Authorization bearer token."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
