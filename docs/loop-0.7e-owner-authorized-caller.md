# Loop 0.7E: owner-authorized caller from a secret store

Loop 0.7D verified live discovery and controlled publication, but the two student-visible materials
were posted through the Classroom teacher interface: the unattended POST path had no caller
identity, and none was invented to close a test. This increment supplies that identity.

## The choice: the owner's own credential, not domain-wide delegation

Two channels can call an owner-only Apps Script web app.

| Channel | What it grants | Verdict |
|---|---|---|
| Service account with domain-wide delegation | Standing authority to impersonate **any** user in the domain for the granted scopes | Supported, not the default |
| The deployment owner's own OAuth credential | Exactly what that one account consented to, revocable by that account alone | **Default** |

The repository's contract already says to use the minimum scope for the active increment. The same
reasoning applies to identity: one call to a web app that the owner owns does not justify a
domain-level grant that outlives it. The owner authorizes the operator application once, and the
resulting refresh token is the durable credential.

Delegation is not removed — a Workspace that already has it configured keeps working — but the
owner-authorized channel wins whenever its secrets are present.

## Where the credential lives

Three secrets define the channel, and none of them is ever in Git:

| Secret | Purpose |
|---|---|
| `MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_ID` | OAuth client id of the operator application |
| `MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_SECRET` | OAuth client secret |
| `MEDSEMIOTICS_CLASSROOM_OAUTH_REFRESH_TOKEN` | Refresh token the owner consented to |

They are read through a `SecretSource`, which has two shapes because a secret manager has two
shapes at runtime:

- **Environment variables** — a Secret Manager version exposed as an env var, or a local operator
  shell.
- **A mounted directory** — `MEDSEMIOTICS_CLASSROOM_SECRET_DIR` points at a volume where each file
  is named after its secret. This is how Cloud Run and Kubernetes mount secret versions.

A mounted file wins over an environment variable of the same name, so rotating a version in the
secret manager takes effect without redeploying to change a variable. Nothing is cached: the next
read sees the rotated value. No secret-manager SDK is added as a dependency — both shapes are the
platform's own delivery mechanisms.

`client_secret` and `refresh_token` are held as `SecretStr`, so no log line, traceback, or
serialized model can carry their values, and every failure path reports the exception class only.

## Minting the credential, once

```bash
python scripts/classroom_owner_authorize.py
```

Run it signed in as the Workspace account that owns the deployment. It opens the consent screen,
requests offline access, and prints the refresh token to store in the secret manager. The printed
value is a credential: store it immediately, never paste it elsewhere, and revoke it from the
account's security settings if it is ever exposed.

## Fail-closed rules

- A store holding **none** of the three secrets means the channel is not configured, and the
  delegated channel may be used instead.
- A store holding **some but not all** of them is a misconfiguration and raises, rather than
  silently downgrading to the delegated channel. A half-rotated secret must never change which
  identity is calling.
- With **neither** channel configured, the error names both, so the operator knows the two ways to
  proceed.
- `describe_operator_channel()` reports which channel a configuration selects — `owner-authorized`,
  `service-account-delegation`, or `unconfigured` — without reading any secret value, so a
  verification record can state which identity ran.

## Closing the Loop 0.7D gap

With the channel configured, the operator scripts reach the deployment unattended:

1. `python scripts/classroom_read_smoke.py` — metadata-only discovery, redacted evidence.
2. `python scripts/classroom_material_publish_smoke.py` — one approved material, ledger-backed.
3. Re-run the same publication and confirm the ledger refuses it before Google is contacted.

Record the channel name from `describe_operator_channel()` alongside the existing evidence. Only
once step 2 has run through the backend POST should the `0.7D` row lose its "backend POST pending"
qualifier.

## Exit criteria

- an owner-authorized channel that creates no standing domain authority;
- secrets read from environment variables or a mounted secret-manager volume, with the mount
  winning and no value cached;
- secret fields that cannot be printed, serialized, or leaked through an error;
- partial configuration that fails closed instead of falling back;
- a one-time consent script that stores nothing in the repository;
- full pytest, Ruff, and strict mypy quality gates, with no network access in tests.
