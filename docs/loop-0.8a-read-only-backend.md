# Loop 0.8A: the read-only backend contract

Master loop 10 accepts an architecture where ChatGPT Work and Claude Cowork are interfaces, not
credential holders: both "consume the same minimized backend contracts". Until now there was no
such contract — the API served a health check, and everything useful ran from operator scripts on a
workstation. This increment supplies the contracts a phone can open.

## What it serves

Four read-only endpoints, all derived from tracked configuration:

| Endpoint | Answers |
|---|---|
| `GET /v1/semester` | Which semester is active and which courses it has |
| `GET /v1/courses/{code}/state` | What has been taught, what is pending, what comes next |
| `GET /v1/courses/{code}/next-topic` | The next required topic **with its curated guide** |
| `GET /v1/courses/{code}/guides/{topic_id}` | The curated guidance for one topic |

`next-topic` is the one a teacher opens before class: objectives, critical points, questions to ask,
pitfalls to anticipate, and materials to bring — the same catalog content the repository already
tracks, reached in one request.

`GET /health` stays unauthenticated so a platform health probe works.

## What it deliberately is not

- **No Google credential.** The backend reads tracked configuration from disk. It calls no Google
  API, holds no OAuth token, and cannot publish anything.
- **No writes.** Every endpoint is a `GET`. Classroom and Calendar changes keep going through the
  approved boundaries of `0.6E`–`0.7E`, with named human approval.
- **No student data.** The responses carry course metadata, topic identifiers, counts, and curated
  teaching content. Rosters, submissions, and grades are not reachable through this surface because
  they are not reachable by the code behind it.

## Access control

A caller presents `Authorization: Bearer <token>`. The token is read from the same secret store the
Classroom caller uses — `MEDSEMIOTICS_API_TOKEN`, from an environment variable or a mounted
secret-manager volume — and compared in constant time.

A backend with **no token configured refuses to serve academic state at all**, answering `503` with
the name of the variable to configure. A misconfigured deployment therefore cannot silently become a
public one; the failure is loud and specific instead.

Errors never echo a filesystem path: a missing course or catalog answers `404` naming only what the
caller asked for and the error class.

## Running it

Locally:

```bash
MEDSEMIOTICS_API_TOKEN=$(openssl rand -hex 32) \
  uv run uvicorn medsemiotics.api.app:app --port 8080
curl -H "Authorization: Bearer $MEDSEMIOTICS_API_TOKEN" \
  http://localhost:8080/v1/courses/NEURO/next-topic
```

On Cloud Run, the container now ships `config/` — without it every read endpoint would answer `404`
in the deployed image — and the token comes from Secret Manager, either as an environment variable
or mounted through `MEDSEMIOTICS_CLASSROOM_SECRET_DIR`. `MEDSEMIOTICS_CONFIG_ROOT` overrides where
tracked configuration is read from.

## How a mobile surface consumes it

The interface holds the backend token only. It asks the backend what to teach next and shows the
curated guidance; it never receives a Google credential, and any Classroom or Calendar change it
proposes still has to travel the approved, named-approval path. That is the boundary master loop 10
already committed to, now expressed as an actual contract.

## Exit criteria

- read-only contracts for semester, course state, next topic, and curated guides;
- bearer-token access from the secret store, compared in constant time;
- fail-closed refusal to serve state when no token is configured;
- errors that name neither a filesystem path nor a secret;
- tracked configuration shipped in the container image;
- full pytest, Ruff, and strict mypy quality gates, with no network access in tests.
