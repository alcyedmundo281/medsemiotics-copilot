# Loop 0.6F: authenticated invocation and live verification

Loop 0.6F closes the gap between the contracts of `0.6A`–`0.6E` and a real Google Workspace: the
authenticated call path, the read verification procedure, and one narrowly controlled write.

## Why an owner-only deployment needs this

Apps Script enforces web-app access **before** `doGet` runs. An unauthenticated caller is not given
an error: it is redirected to a Google sign-in page and receives HTML. A transport that simply
parsed the body would report a confusing JSON error for what is really an authorization failure.

`AuthenticatedAppsScriptTransport` therefore treats every one of Google's refusals as an
authentication failure with an actionable message: a 3xx redirect, a 401 or 403, and an HTML body
on a 200. It refuses outright to send a bearer token to a non-HTTPS URL, and `UrllibHttpSender`
never follows a redirect, so a token cannot be replayed to whatever a redirect points at.

Nothing that could identify the deployment or the caller reaches an error: messages carry the
status code, the content type, and the exception class only — never the execution URL, the token, a
response body, or a chained cause.

## Where the identity comes from

`BearerTokenProvider` is the seam. `GoogleCredentialsTokenProvider` adapts any google-auth
credentials object, refreshing it when needed and never persisting the token. The operator decides
which identity that is; the repository holds no credential and no opinion beyond the boundary.

The intended arrangement is a service account with domain-wide delegation impersonating the
dedicated Workspace user that owns the deployment, with the deployment shared with that user only.

> The caller's token scopes are the part most likely to need adjustment on first contact. Start
> with `openid` and `userinfo.email` (the script's default), and if the deployment answers with a
> sign-in page while the identity is correct, set `MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES` to the
> scopes your Workspace requires for web-app invocation. A sign-in page means the request reached
> Google unauthenticated — it never means the Classroom scope of `0.6A` is wrong, because that
> scope is consumed by the deployment, not by the caller.

## Verification procedure

Run from the dedicated Workspace operator's environment, never from CI:

```bash
python scripts/classroom_read_smoke.py
```

Required environment, all outside Git:

| Variable | Purpose |
|---|---|
| `MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_URL` | Apps Script execution URL |
| `MEDSEMIOTICS_CLASSROOM_APPS_SCRIPT_DEPLOYMENT_ID` | Deployment identifier, matching the URL |
| `MEDSEMIOTICS_CLASSROOM_SERVICE_ACCOUNT_FILE` | Service account key file |
| `MEDSEMIOTICS_CLASSROOM_IMPERSONATED_SUBJECT` | Workspace user to impersonate |
| `MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES` | Optional caller scopes override |

Exit codes: `0` verified, `1` the deployment refused or could not be read, `2` the operator
environment is incomplete.

## Evidence is redacted by construction

The script prints the Loop 0.6C `audit_summary()` and nothing else: provider, capture timestamp,
approved Classroom scope, course count, per-lifecycle counts, and the content fingerprint. Course
names, identifiers, links, the execution URL, and the deployment identifier are never printed, so
the output can be pasted into a verification record as-is.

Record one row per verification run:

| Date | Operator | Course count | Lifecycle counts | Fingerprint | Result |
|---|---|---|---|---|---|
| | | | | | |

A repeated run against an unchanged Classroom reproduces the same fingerprint, which is what makes
a second verification meaningful rather than ceremonial.

## Write verification: one coursework draft

The accountable owner approved adding the Classroom write scope, so this increment also applies
exactly one coursework item in `DRAFT` state.

### The scope, and why it is this one

`https://www.googleapis.com/auth/classroom.coursework.students` is the narrowest scope Google
offers for creating coursework in a course the account teaches. Two alternatives were considered
and rejected:

- `classroom.coursework.me` grants a user authority over *their own* coursework as a student. It
  cannot create an assignment for a course the account teaches, so it does not implement this
  operation at all.
- `classroom.courseworkmaterials` carries no grade authority, but creates course *material*: no due
  date, no submissions, and no relationship to the coursework draft Loop 0.6E models.

The chosen scope also grants grade authority at the OAuth level. Google offers no narrower scope
that separates the two, so the boundary is enforced by construction instead:

- **MedSemiotics never holds the scope.** The Apps Script deployment does. The repository stores no
  Classroom credential of any kind.
- **The deployment exposes one write.** `doPost` accepts only `coursework_draft_create`, always
  sets `state: 'DRAFT'`, and never reads or sets `maxPoints` or any grading field.
- **The policy denies grades explicitly.** `ClassroomAccessPolicy` grants the write operation only
  for the exact category `own_coursework_draft`; declaring `grades`, `submissions`, `rosters`, or
  existing `coursework` alongside it is denied, as is declaring the write as read-only.
- **The plan cannot express a grade.** `ClassroomActionPlan` has no grading field and rejects one.
- **The reply is re-validated.** `AppsScriptCourseworkWriter` rejects any answer whose item is not
  `DRAFT`, that carries a grading field, or that declares a broader scope.

### What must be true before anything is sent

The writer verifies both decisions itself, before the transport is touched: the Loop 0.6A access
decision must be allowed, for this operation, limited to `own_coursework_draft`, with exactly the
write scope; and the Loop 0.6E action decision must be `authorized` and carry the identity of the
exact plan supplied. An `already_applied` decision is refused rather than re-sent.

### Verification procedure

```bash
python scripts/classroom_write_smoke.py \
    --course-id <classroom course id> --topic-id <tracked topic> \
    --title "..." --approved-by "Name of the approver"
```

The script prints the plan's `identity_key` and `content_fingerprint` before applying, then the
ledger entry the operator must keep:

| Field | Meaning |
|---|---|
| `identity_key` | Identity that makes a repeat run a no-op |
| `external_course_id` | Course the draft was created in |
| `external_reference` | Classroom identifier of the created draft |
| `applied_at` / `applied_by` | When it was applied, and who approved it |

Recording that entry is what closes the idempotency loop: supplied to
`ClassroomActionAuthorizer` on a later run, the same plan returns `already_applied` and no second
draft is created.

### Verification checklist

1. Run the read verification first; a linked course id comes from the coordination view.
2. Apply one draft with the script and record the ledger entry.
3. Confirm in Classroom that the item exists, is a draft, and shows no points.
4. Re-run the same command with the recorded ledger entry supplied and confirm it is refused as
   already applied rather than duplicating the draft.

## Exit criteria for this increment

- authenticated invocation with a bearer token, refusing plaintext URLs and never following
  redirects;
- every Google refusal — redirect, 401, 403, sign-in HTML — reported as an authentication failure;
- no URL, token, body, or chained cause in any error;
- an operator script producing redacted, reproducible evidence;
- one write operation, added to the access policy as its own exactly-scoped allowance, that cannot
  be declared read-only and cannot carry a grade, roster, submission, or existing-coursework
  category;
- a write boundary that re-verifies both decisions before sending, sends no grading field, and
  refuses any reply that is not a draft;
- a ledger entry returned by the write itself, so the next run of the same plan is a no-op;
- hermetic tests, including a localhost server proving the sender's redirect and error handling;
- full pytest, Ruff, and strict mypy quality gates.
