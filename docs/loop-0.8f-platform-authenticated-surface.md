# Loop 0.8F: two headers, two authorizations

The first real deployment surfaced a design collision. The Workspace organization policy forbids
granting `allUsers` the right to invoke a Cloud Run service, so the service authenticates its
callers itself — and Cloud Run reads that identity from `Authorization`, which is exactly where the
backend expected its own token. One header, two claimants.

## The fix

The backend token now travels in a dedicated header, `X-MedSemiotics-Token`, and `Authorization`
stays free for whatever the platform puts there. The bearer form still works for deployments where
nothing else claims that header, so nothing that already worked breaks.

When both are present, the dedicated header wins. That ordering is the point: a platform identity
token sitting in `Authorization` must never be *mistaken* for a backend token, not even by
accident, and it never is.

## Two layers, not two options

These are independent authorizations, and both apply:

| Layer | Question it answers | Where it lives |
|---|---|---|
| Platform (Cloud Run IAM) | May this caller reach the service at all? | `Authorization` |
| Backend token | May this caller read academic state? | `X-MedSemiotics-Token` |

The deployment that forced this change is therefore *stronger* than the one originally documented:
an unauthenticated request never reaches the application, and a request that does reach it still
has to present the backend token. The organization policy that blocked `allUsers` improved the
posture rather than obstructing it.

## What a surface sends

`BackendClient` takes an optional `identity_token`. With it, the client sends both headers; without
it, just the backend token. Neither ever appears in a message: a `403` from the platform explains
that an identity token is needed and names the variable that carries it, while a `401` from the
backend says to rotate the backend token — and neither error echoes either value.

```bash
export MEDSEMIOTICS_API_BASE_URL=https://<service>.run.app
export MEDSEMIOTICS_API_TOKEN=$(gcloud secrets versions access latest --secret=medsemiotics-api-token)
export MEDSEMIOTICS_API_IDENTITY_TOKEN=$(gcloud auth print-identity-token)

python scripts/backend_query.py /v1/courses/NEURO/next-topic
```

Identity tokens are short-lived, so a surface refreshes that variable rather than storing it.

## Exit criteria

- the backend token accepted in a dedicated header, with the bearer form still working;
- the dedicated header preferred, so a platform token is never read as a backend token;
- a client that sends both, and errors that distinguish a platform refusal from a token rejection
  without echoing either value;
- full pytest, Ruff, and strict mypy quality gates.
