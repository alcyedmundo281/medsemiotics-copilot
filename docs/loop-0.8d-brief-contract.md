# Loop 0.8D: the class brief contract

`GET /v1/courses/{code}/brief` completes what a teacher opens before class: the topic is selected
automatically from the reconciled schedule and the tracked academic state, then composed with the
curated guide into one reviewable brief.

## Always a draft

The response says so three ways, because a brief that could be mistaken for a published one is the
failure mode worth designing against:

- `status` is `draft` and `requires_approval` is `true`, on every response;
- the `note` states that publishing to Calendar or Classroom is a separate action needing a named
  human approval;
- the chain that produced it **has no publishing collaborator wired into it at all**.

That last point is the one that matters. `TeachingCoachPreviewService` is composed here from the
reconciliation service, the academic repositories, the curated catalog, and the agent — and nothing
else. The publish path of Loop 0.5C exists, is separately approved, and is simply not reachable from
this endpoint's object graph.

## Automatic topic selection

The caller does not name a topic. The effective teaching day service resolves which class falls on
the requested date, the tracked syllabus and teaching log decide which topic that class is at, and
the curated catalog supplies the guidance. A day with no class answers `404` naming the date rather
than inventing a brief for it; a topic the catalog does not cover fails closed the same way.

`date` defaults to today in the academic timezone.

## Credentials

Resolving *which* class falls on a date needs the reconciled schedule, so this endpoint requires the
Loop 0.8C Calendar credential — `calendar.readonly`, from the secret store. With none configured it
answers `503` naming the three secrets. It still holds no Classroom credential and still cannot
write anywhere.

## Exit criteria

- automatic topic selection from reconciled schedule and tracked state, with no caller-supplied
  topic;
- a draft marked as one in status, flag, and prose, produced by a chain with no publish path;
- `404` for a day without class, an uncovered topic, or an unknown course, naming neither a
  filesystem path nor an invented brief;
- `503` naming the Calendar secrets when the credential is absent;
- full pytest, Ruff, and strict mypy quality gates, with the Calendar reader injected in tests.
