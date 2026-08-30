# Loop 0.6F: authenticated invocation and live read verification

Loop 0.6F closes the gap between the contracts of `0.6A`–`0.6E` and a real Google Workspace. This
increment delivers the authenticated call path and the verification procedure for the **read**
side. The narrowly controlled write verification is the remaining half and is described at the end.

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

## Remaining half: write verification

Creating one coursework draft would exercise the Loop 0.6E plan, its named approval, and its
idempotency ledger against a real course. It is deliberately **not** in this increment, because it
requires adding a Classroom **write** scope to the authorization boundary that Loop 0.6A
deliberately restricted to `classroom.courses.readonly`.

That is an expansion of OAuth authority, and it needs an explicit decision by the accountable
owner before any code requests it. When it is taken, the write verification must keep every
property established here: one action, named approval bound to the reviewed content, idempotency
against the local ledger, redacted evidence, and no grade or student-visible publication.

## Exit criteria for this increment

- authenticated invocation with a bearer token, refusing plaintext URLs and never following
  redirects;
- every Google refusal — redirect, 401, 403, sign-in HTML — reported as an authentication failure;
- no URL, token, body, or chained cause in any error;
- an operator script producing redacted, reproducible evidence;
- hermetic tests, including a localhost server proving the sender's redirect and error handling;
- full pytest, Ruff, and strict mypy quality gates.
