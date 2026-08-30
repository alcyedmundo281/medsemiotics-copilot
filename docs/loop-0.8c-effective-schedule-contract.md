# Loop 0.8C: the reconciled schedule contract

Loops `0.8A` and `0.8B` served everything a phone needs that requires no credential. This increment
adds the one thing that does: the **effective schedule** — the tracked baseline reconciled with
Calendar evidence, so cancellations, makeup sessions, and exact meeting times become visible.

## The credential, and what it can do

`GET /v1/courses/{code}/effective-schedule` is the only endpoint that contacts Google. It needs a
credential, and that credential is deliberately narrow:

| Property | Choice |
|---|---|
| Scope | **Fixed** to `calendar.readonly`, not configurable |
| Identity | The Calendar owner's own consented credential, as in Loop 0.7E |
| Storage | The same secret store: environment variables or a mounted volume |
| Relationship to Classroom | A **separate** credential — one never accumulates both authorities |

`CalendarReadCredentials` exposes `scopes` as a fixed tuple rather than a field, so no configuration
change and no caller can widen it. The model forbids extra inputs, so an attempt to pass a broader
scope is rejected rather than ignored. Both secret fields are `SecretStr`.

The backend therefore gains exactly one new power: reading the Calendar it was already bound to. It
still holds no Classroom credential, still cannot write anywhere, and still exposes no student data.

| Secret | Purpose |
|---|---|
| `MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_ID` | OAuth client id |
| `MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_SECRET` | OAuth client secret |
| `MEDSEMIOTICS_CALENDAR_OAUTH_REFRESH_TOKEN` | Refresh token consented for `calendar.readonly` |

Mint the refresh token with the Loop 0.7E consent script, run with the Calendar scope:

```bash
MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_ID=... \
MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_SECRET=... \
MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES=https://www.googleapis.com/auth/calendar.readonly \
  python scripts/classroom_owner_authorize.py
```

Store the printed token under the **Calendar** secret names above, keeping the two channels apart.

## Degrading honestly

With no Calendar credential configured, the endpoint answers `503` naming the three secrets and
pointing at `/v1/courses/{code}/schedule`, which still serves the planned baseline. A phone is never
left with a silent half-answer: either the reconciliation happened, or the response says why it did
not and where the unreconciled truth lives.

The reconciliation itself keeps the invariant master loop 3 established: **an unobserved baseline
date remains a scheduled class**. An empty Calendar does not erase the semester.

`days` bounds the window between 1 and 120.

## Still absent: the full brief

The Teaching Coach brief composes this reconciled schedule with the curated guide and the academic
state. Now that the schedule is reachable, the brief is the natural next increment — but it is a
draft that must never be mistaken for a published one, and that distinction deserves its own
contract rather than being appended here.

## Exit criteria

- a Calendar read credential from the secret store, scoped to `calendar.readonly` by construction;
- a credential separate from the Classroom caller, with both secret fields unprintable;
- partial configuration that fails closed;
- an endpoint that reconciles the baseline with Calendar evidence within a bounded window;
- an explicit `503` naming the missing secrets and the baseline endpoint when unconfigured;
- full pytest, Ruff, and strict mypy quality gates, with no network access in tests.
