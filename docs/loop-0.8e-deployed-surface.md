# Loop 0.8E: the deployed surface

The contracts of `0.8A`–`0.8D` were built to be consumed from a phone. This increment makes that
consumption real: it closes the one thing that should not be public on a deployed service, adds the
client a conversational surface actually uses, and writes down how to deploy it.

## The schema is not public either

`/openapi.json`, `/docs`, and `/redoc` were served without a token. On a deployed service that
publishes the full shape of the API — every path, every field — to anyone who asks.

- `/openapi.json` is now guarded by the **same token as the data**. A conversational surface fetches
  it once to learn what it may call; an unauthenticated caller learns nothing about the surface.
- `/docs` and `/redoc` are **disabled outright**. They fetch the schema from the browser without a
  bearer header, so against a token-guarded backend they could only ever render an error.
- `/health` stays public, because a platform health probe cannot present a token.

## How Claude Cowork consumes the contract

Cowork is an interface, not a credential holder. It gets exactly one secret — the backend token —
and never a Google credential. Concretely:

1. **Give the session the token and the URL**, through its environment or a mounted secret
   directory, never by pasting them into the conversation:

   ```bash
   export MEDSEMIOTICS_API_BASE_URL=https://<your-service>.run.app
   export MEDSEMIOTICS_API_TOKEN=...        # or MEDSEMIOTICS_CLASSROOM_SECRET_DIR=/run/secrets
   ```

2. **Let it ask the backend**, with the client this increment ships:

   ```bash
   python scripts/backend_query.py /v1/courses/NEURO/next-topic
   python scripts/backend_query.py /v1/coordination
   python scripts/backend_query.py "/v1/courses/NEURO/brief?date=2026-09-08"
   ```

   The token is read from the secret store and never printed. Every failure explains itself without
   echoing it: a rejected token says to rotate it, an unconfigured backend relays which secret is
   missing, and an unreachable one names only the exception class.

3. **Let it orient itself** with `python scripts/backend_query.py /openapi.json`, which returns the
   contracts it may call — and, by omission, the ones it may not.

`BackendClient` issues `GET` requests and nothing else, because the backend serves nothing else.
A surface therefore cannot publish, cannot reach Classroom, and cannot see student data, no matter
what it is asked to do. Publishing remains what it has been since Loop 0.5C: a separate action with
a named human approval, taken through the operator path.

The same three steps apply to ChatGPT Work or any other surface. What changes between them is the
conversation, not the authority.

## Deploying it

```bash
gcloud run deploy medsemiotics-backend \
  --source . \
  --region <region> \
  --no-allow-unauthenticated \
  --set-secrets MEDSEMIOTICS_API_TOKEN=medsemiotics-api-token:latest \
  --set-secrets MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_ID=medsemiotics-calendar-client-id:latest \
  --set-secrets MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_SECRET=medsemiotics-calendar-client-secret:latest \
  --set-secrets MEDSEMIOTICS_CALENDAR_OAUTH_REFRESH_TOKEN=medsemiotics-calendar-refresh-token:latest
```

Notes that matter:

- The image ships `config/`, so the read endpoints have tracked configuration to serve.
- The Calendar secrets are optional: without them the reconciled schedule and the brief answer `503`
  naming what is missing, and every other contract still works.
- Rotating a secret version needs no redeploy when the secrets are mounted as a volume and
  `MEDSEMIOTICS_CLASSROOM_SECRET_DIR` points at it; nothing is cached.
- `--no-allow-unauthenticated` adds platform-level access control *in front of* the backend token.
  The token is not a substitute for it; both are cheap.

## Exit criteria

- the API schema served only to an authenticated caller, with the browser doc pages disabled;
- a client that adds the bearer header, issues GETs only, and keeps the token out of every message;
- an operator script that reads the token from the secret store and never prints it;
- a deployment runbook, and a written path for how a conversational surface consumes the contract;
- full pytest, Ruff, and strict mypy quality gates, with the transport injected in tests.
