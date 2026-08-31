# Loop 0.8H: one command for the operator

Provisioning the backend took a dozen commands across three sessions, and two of the failures along
the way were ordering mistakes rather than real problems: a project not set, a repository not
cloned, a build account without permission. Those belong in a script, not in a person's memory.

`scripts/cloud_run_setup.sh` provisions and deploys everything, and verifies the result.

## What it does

```bash
bash scripts/cloud_run_setup.sh
```

In order: enables the four APIs, ensures the runtime service account exists, grants the build
account the role it needs to build from source, ensures the backend-token secret exists — generating
one only when there is no version yet — mounts the Calendar credential if one is available, deploys,
and then checks both authorization layers.

Every step is idempotent. Run it again after any change and it converges rather than duplicating or
failing.

## The Calendar credential stays optional

If `~/.config/gcloud/application_default_credentials.json` holds a refresh token, the script mounts
the three Calendar secrets and says so. If not, it says that too, and deploys without them: every
contract that needs no Calendar still works, and the two that do answer `503` naming what is
missing. Nothing is half-configured silently.

To include it, authorize once as the account that can read the course calendars:

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/calendar.readonly,openid,https://www.googleapis.com/auth/userinfo.email
```

That step is deliberately outside the script: minting a credential requires a person's browser
session and their consent, which is not something a script — or an assistant — can do on their
behalf.

## What it prints, and what it never prints

It prints the project, region, service, runtime account, whether a Calendar credential was found,
the deployed URL, and four status codes: `200`, `401`, `403`, and the brief's `200` or `503`. Those
four lines are the verification evidence.

It never prints the backend token, the Calendar client secret, or the refresh token. Secret values
move from the credential file into Secret Manager through a pipe, and the export instructions at the
end read them back from Secret Manager rather than echoing them.

## Exit criteria

- one command that provisions, deploys, and verifies;
- idempotent throughout, safe to re-run;
- the Calendar credential optional, with its absence reported rather than silently assumed;
- no secret value printed at any point;
- the one step a script cannot own — human consent — left explicitly to the operator.
