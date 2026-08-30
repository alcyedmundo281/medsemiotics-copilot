# Loop 0.6B: persistent Apps Script read boundary

Loop 0.6B turns the Loop 0.6A policy into an executable, metadata-only course discovery read.
It adds no OAuth token to MedSemiotics, no Classroom write path, and no student-level data.

## Where the authorization lives

The dedicated Workspace account owns a private Apps Script web app
(`scripts/apps_script/classroom_course_discovery.gs`). That deployment holds the persistent
Classroom grant and is the only component that talks to Google. MedSemiotics reads the deployment
through an injected `AppsScriptTransport`, so the repository never stores a Classroom OAuth client,
refresh token, or live API response.

The deployment is pinned to a single scope in `appsscript.json`:

```text
https://www.googleapis.com/auth/classroom.courses.readonly
```

Its location is configuration, never tracked content:

| Variable | Purpose |
|---|---|
| `MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_URL` | HTTPS Apps Script web app execution URL |
| `MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_DEPLOYMENT_ID` | Deployment identifier recorded in the audit trail |

`load_apps_script_deployment()` fails closed when either value is missing and never echoes the
configured URL in an error message. `AppsScriptDeployment` accepts only HTTPS URLs on
`script.google.com` or `script.googleusercontent.com`, so a read cannot be redirected to another
host.

## Two authorizations before one read

`ClassroomCourseDiscoveryService.discover_courses()` authorizes twice before any transport call:

1. the Coordination capability `coordination.classroom-course-discovery` at `OBSERVE`, through the
   four-C `AgentCapabilityFramework`;
2. the Loop 0.6A `ClassroomAccessPolicy`, declaring `course_metadata`, the exact readonly scope,
   one accountable requester, and `external_mutation=false`.

`AppsScriptCourseDiscoveryClient` re-verifies the resulting `ClassroomAccessDecision` itself. A
denied decision, a broader approved category, or a broader approved scope raises
`GoogleClassroomBoundaryError` before the deployment is contacted, so the adapter cannot be driven
outside the policy even by a caller that bypasses the service.

## Sanitized payload contract

The deployment answers with exactly four envelope fields — `operation`, `scopes`,
`external_mutation`, `courses` — and each course carries at most five metadata fields:
`id`, `name`, `section`, `course_state`, `alternate_link`.

The client enforces that allowlist again on arrival. Any other field fails the read:

- a prohibited field (`students`, `teachers`, `roster`, `enrollmentCode`, `ownerId`,
  `teacherGroupEmail`, `courseGroupEmail`, `courseWork`, `submissions`, `grades`, `teacherFolder`,
  and similar) is rejected by name;
- any unrecognized field is rejected as well, so a future Classroom response cannot widen the
  boundary silently;
- `external_mutation` must be `false` and `scopes` must equal the single readonly scope;
- non-string course values, unsupported course states, and duplicate course identifiers fail
  closed rather than being coerced.

The result is an immutable `ClassroomCourseDiscovery` with a timezone-aware read timestamp, the
requester, the deployment identifier, the approved scopes, and courses ordered deterministically by
name and identifier.

## Explicitly out of scope

- rosters, student identifiers, coursework, announcements, submissions, and grades;
- Classroom, Drive, or Calendar mutation of any kind;
- persisting Classroom content to the repository;
- provider-neutral snapshot normalization (Loop 0.6C) and the coordinated read view (Loop 0.6D);
- live verification against a real deployment, which belongs to Loop 0.6F.

## Public/private separation

The contract, adapter, Apps Script source, and sanitized fixtures are public. The deployment URL,
deployment identifier, OAuth client files, tokens, live responses, and every course-level or
student-level value stay outside Git, in the dedicated Workspace account or a runtime secret store.

## Exit criteria

- immutable, strict domain models for sanitized course metadata and discovery provenance;
- deployment descriptor restricted to HTTPS Apps Script hosts, configured outside Git;
- decision re-verification that fails closed before any transport call;
- allowlisted envelope and course fields with explicit prohibited-data rejection;
- deterministic ordering and duplicate rejection;
- full pytest, Ruff, and strict mypy quality gates with no network access in tests.
