# Loop 0.6E: one approved, idempotent Classroom action

Loop 0.6E defines what a single Classroom write may be and what must be true before it could run.
It ships no execution adapter: a plan is a proposal and an authorization is a decision, not a call.
Executing one, against a real course, is Loop 0.6F.

## Exactly one action, and only one kind

`ClassroomActionPlan` describes one coursework item created in **draft** state — visible to
teachers, not published to students. A batch is not representable: the plan is a single object, not
a list, and there is no batch entry point to call.

The model has no grading field of any kind, and `extra="forbid"` means a caller that tries to smuggle
`max_points`, `grade`, `assigned_students`, or `published` is rejected rather than silently ignored.
An action type outside the coursework-draft contract raises `ClassroomActionAuthorizationError`
instead of being evaluated.

Planning refuses a course that is not decisively linked to Classroom by the Loop 0.6D view — a
`not_found`, `ambiguous`, or `not_read` link is never good enough to write against — a course with
no tracked syllabus topics, and a due date before the plan was prepared.

## Approval binds to the reviewed content

Every plan carries two digests that answer different questions:

- `identity_key` — semester, course, Classroom course id, topic, and the normalized title. It is
  what the work *is*.
- `content_fingerprint` — the identity plus the exact title, instructions, and due date. It is what
  a reviewer *read*.

`ClassroomActionApproval` records a named approver, a timezone-aware timestamp, and the
`content_fingerprint` they approved. Editing the instructions or the due date after approval
changes the fingerprint, so the authorizer denies it and asks for a re-review. Approval is what
supplies the `EXECUTE_WITH_APPROVAL` authorization context to the four-C capability
`coordination.classroom-action`, which is registered with that autonomy as both its floor and its
ceiling and is not eligible for trusted automation.

## Idempotency without reading Classroom

Coursework reads are outside the OAuth scope Loop 0.6A authorizes, so idempotency cannot be decided
by querying Classroom — and widening the scope to check would be a worse trade than the duplicate it
prevents. It is decided instead against `ClassroomActionRecord`, MedSemiotics' own ledger of actions
it already applied, matched on `identity_key`.

A plan whose identity is already in the ledger returns `already_applied` with the previously created
reference, never a second write. Because identity excludes instructions and due date, correcting a
draft's wording does not create a duplicate; changing the title, topic, course, or semester
correctly produces a different action.

## Explicitly out of scope

- executing anything: no Classroom write adapter, transport, or credential is added here;
- grade publication, points, and any student-visible publication;
- bulk or multi-action plans;
- deleting or modifying Classroom items MedSemiotics did not create;
- rosters, student identifiers, submissions, and every read beyond Loop 0.6A's course metadata.

## Exit criteria

- immutable, strict single-action plan, approval, ledger, and decision models;
- deterministic identity and content digests with distinct, tested responsibilities;
- approval bound to reviewed content, so an edited plan is denied;
- idempotency decided against the local ledger, returning the prior reference;
- `EXECUTE_WITH_APPROVAL`-only capability that cannot be automated;
- full pytest, Ruff, and strict mypy quality gates with no network access in tests.
