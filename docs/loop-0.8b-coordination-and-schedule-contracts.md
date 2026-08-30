# Loop 0.8B: coordination and planned schedule contracts

Loop 0.8A answered *what do I teach next*. This increment answers the two questions that follow on a
working day: **why is something not working**, and **when is the next class**. Both stay inside the
0.8A boundary — read-only, tracked configuration only, no Google credential.

## What it adds

| Endpoint | Answers |
|---|---|
| `GET /v1/coordination` | Is each active course wired for coordinated support, and what is missing |
| `GET /v1/courses/{code}/schedule` | The next planned class dates, from the tracked baseline |

`/v1/coordination` serves the Loop 0.6D view: per course, the Classroom binding, the tracked
Calendar binding, progress counts, an explicit readiness, and the gaps that keep it from being
ready. Courses skipped as inactive are listed separately.

`/v1/courses/{code}/schedule` returns the baseline window and the next planned dates, with `limit`
between 1 and 50.

## Two honest labels

Both responses carry a `note` saying what was and was not consulted, because both could otherwise be
mistaken for more than they are:

- **Classroom always reports `not_read`.** The coordination view needs an authorized Classroom
  snapshot, and this backend holds no Google credential by design. The status is the truthful
  outcome, not a failure — and it comes with the reason, so a reader is not left guessing.
- **Planned dates are not confirmed dates.** The baseline schedule is date-only. Cancellations,
  makeup sessions, and exact meeting times are operational Calendar evidence, which this backend
  does not read.

A course whose calendar binding is absent, or that is inactive, is skipped rather than failing the
whole view: one unconfigured course must not hide the state of the others.

## Still deliberately absent

The Calendar-reconciled effective schedule and the full Teaching Coach brief both depend on live
Calendar evidence. Serving them means giving this backend a Google credential, which is exactly what
the 0.8A boundary refuses. They belong to an increment that runs with those credentials and keeps
the approval path intact — not to this one.

## Exit criteria

- coordination and planned-schedule contracts behind the same bearer token as 0.8A;
- an explicit note on each response naming what was consulted and what was not;
- Classroom bindings that report `not_read` with a reason rather than implying a failed lookup;
- inactive courses and absent calendar bindings skipped without failing the view;
- a bounded, validated `limit` on the schedule window;
- full pytest, Ruff, and strict mypy quality gates, with no network access in tests.
