# Loop 0.8: live backend verification

The read-only backend was deployed and exercised against a real Cloud Run service. This note records
what was verified, what was not, and the two defects the deployment found that the test suite had
not.

## What was verified

| Item | Value |
|---|---|
| Date | 2026-08-31 |
| Platform | Google Cloud Run, `us-central1` |
| Revision | `medsemiotics-backend-00003-q5z`, 100% of traffic |
| Runtime identity | A dedicated service account whose only grant is `secretAccessor` on the API-token secret |
| Backend token | Secret Manager version, mounted as an environment variable |
| Platform access | Authenticated callers only; the organization policy forbids `allUsers` |

Three requests to `/v1/semester`, differing only in which credential was withheld:

| Request | Result | What it proves |
|---|---|---|
| Both credentials | `200` with semester `2026-2`, courses GASTRO and NEURO | The contract serves tracked configuration from the deployed image |
| Platform identity only | `401` | The platform admitted the caller; the backend still refused it |
| Backend token only | `403` | The request never reached the application |

Two independent layers, each refusing on its own. That is the property Loop 0.8F set out to
establish, confirmed against the real platform rather than a test double.

## What the deployment found that the tests had not

Live verification earned its keep twice:

- **Loop 0.8F** — the organization policy forbids `allUsers`, so Cloud Run authenticates callers
  itself and reads that identity from `Authorization`: the header the backend token was using. Two
  claimants, one header. The backend token moved to `X-MedSemiotics-Token`.
- **Loop 0.8G** — the first deployed request answered `503 no access token configured` while the
  secret was correctly mounted. Access control read application state that was only wired from
  inside an endpoint body, and a dependency runs before the body it guards. Every test passed
  because every test configured the application by hand first; production never does.

Both were defects in shipped code, invisible to a suite that never started a cold process.

## What is not verified

- `/v1/courses/{code}/effective-schedule` and `/v1/courses/{code}/brief` answer `503` naming the
  missing secrets, because no Calendar credential is configured on this deployment. Their live
  behaviour remains unverified, by design rather than by omission.
- The Classroom write path of Loops 0.6F and 0.7D is untouched by this backend and unaffected by
  this verification.

## Evidence hygiene

This note records status codes, the deployed revision, and the payload shape. The service URL, the
project identifiers, the backend token, and the platform identity token are deliberately absent:
they are private runtime configuration, and the same rule that keeps the Apps Script execution URL
out of Git keeps them out too.
