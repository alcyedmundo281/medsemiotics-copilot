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

`load_apps_script_deployment()` fails closed when either value is missing or invalid, and never
echoes a configured value — in the message or through a chained cause. `AppsScriptDeployment`
accepts only an HTTPS execution URL on `script.google.com`, in the personal
`/macros/s/<deployment_id>/exec` or the Workspace `/a/macros/<domain>/s/<deployment_id>/exec`
form, so a read cannot be redirected to another host. The configured `deployment_id` must equal
the identifier encoded in that URL, so a partially updated configuration after a redeployment
fails closed instead of recording provenance for a deployment that was never read.

Read failures are reported by exception type only. A transport exception frequently embeds the URL
it tried to reach, so neither its message nor its chained cause is propagated.

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
- live verification against a real deployment, which belongs to Loop 0.6F;
- a concrete HTTP transport. Loop 0.6B ships the `AppsScriptTransport` protocol and its
  deterministic validation only.

### Invoking the deployment from a backend

The reference deployment is `Execute as: Me` with `Who has access: Only myself`, which is
deliberate for this increment: the read path is exercised through an injected transport and, during
verification, from the dedicated Workspace account's own authenticated session. That setting cannot
be called by an unattended backend — an anonymous request is redirected to a Google sign-in page
instead of reaching `doGet`.

Loop 0.6F therefore owns authenticated invocation, deferred there deliberately rather than left
undecided, and must settle it before any unattended read: a Google-issued OIDC identity token for
the dedicated Workspace identity, sent as `Authorization: Bearer <id_token>` with the deployment
opened to that identity only, is the intended direction. A shared secret over an owner-only
deployment is not an option — access is enforced before `doGet` runs, so the secret would never be
evaluated. Nothing in this increment should be read as evidence that an unattended cloud read
already works.

## Public/private separation

The contract, adapter, Apps Script source, and sanitized fixtures are public. The deployment URL,
deployment identifier, OAuth client files, tokens, live responses, and every course-level or
student-level value stay outside Git, in the dedicated Workspace account or a runtime secret store.

## Exit criteria

- immutable, strict domain models for sanitized course metadata and discovery provenance;
- deployment descriptor restricted to HTTPS Apps Script execution URLs whose encoded identifier
  matches the configured one, resolved from configuration held outside Git;
- read and configuration failures that withhold the execution URL and every configured value;
- decision re-verification that fails closed before any transport call;
- allowlisted envelope and course fields with explicit prohibited-data rejection;
- deterministic ordering and duplicate rejection;
- full pytest, Ruff, and strict mypy quality gates with no network access in tests.
