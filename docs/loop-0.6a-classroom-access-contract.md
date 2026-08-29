# Loop 0.6A: Google Classroom access contract

Loop 0.6A establishes the policy boundary that must authorize a Classroom adapter before it can
contact Google. It performs no network request and grants no mutation authority.

## Allowed boundary

The only enabled operation is metadata-only course discovery using exactly:

```text
https://www.googleapis.com/auth/classroom.courses.readonly
```

The request must declare one accountable requester, the `course_metadata` category, and
`external_mutation=false`. The resulting capability is Coordination/OBSERVE only.

## Explicitly prohibited

- rosters or enrollment lists;
- student names, identifiers, or email addresses;
- coursework or announcements;
- submissions or student work;
- grades;
- Classroom, Drive, or Calendar mutation;
- additional or broader OAuth scopes.

`ClassroomAccessPolicy.evaluate()` returns an explainable decision. `authorize()` fails before an
integration adapter can run when the declaration exceeds the allowed boundary.

## Public/private separation

The contract, adapter code, tests, and sanitized fixture data may be public. OAuth client files,
refresh tokens, live API responses, private course content, and any student-level data must remain
outside Git. The dedicated Workspace account owns the authorization; repository access never
implies Workspace authority.

## Exit criteria

- immutable, strict domain models for request and decision;
- deterministic exact-scope and exact-category policy;
- OBSERVE-only Coordination capability;
- tests proving broader data, scopes, and all mutations fail closed;
- full pytest, Ruff, and strict mypy quality gates.

Live course discovery belongs to Loop 0.6B and must consume this policy rather than bypass it.
