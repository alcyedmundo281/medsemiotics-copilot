#!/usr/bin/env bash
# RETIRED: the hosted deployment was removed by the owner to avoid recurring cost.
# The supported surface is the local server (scripts/run_local.py). This script is kept for
# reference and will recreate billable resources if it is run.
# Provision and deploy the read-only MedSemiotics backend on Cloud Run.
#
# Usage, from a Cloud Shell session in the repository root:
#
#     bash scripts/cloud_run_setup.sh
#
# Everything here is idempotent: run it again after changing anything and it converges. It never
# prints a secret value, and it creates nothing outside the project you point it at.
#
# The Calendar credential is optional. To include it, authorize once beforehand as the account that
# can read the course calendars:
#
#     gcloud auth application-default login \
#       --scopes=https://www.googleapis.com/auth/calendar.readonly,openid,\
# https://www.googleapis.com/auth/userinfo.email
#
# The script then reads the three values from that file and mounts them. Without it, the backend
# still serves every contract that needs no Calendar, and the two that do answer 503 naming what is
# missing.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-medsemiotics-backend}"
RUNNER_NAME="${RUNNER_NAME:-medsemiotics-runner}"
TOKEN_SECRET="${TOKEN_SECRET:-medsemiotics-api-token}"
ADC_FILE="${ADC_FILE:-$HOME/.config/gcloud/application_default_credentials.json}"

CALENDAR_SECRETS=(
  "medsemiotics-calendar-client-id:client_id:MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_ID"
  "medsemiotics-calendar-client-secret:client_secret:MEDSEMIOTICS_CALENDAR_OAUTH_CLIENT_SECRET"
  "medsemiotics-calendar-refresh-token:refresh_token:MEDSEMIOTICS_CALENDAR_OAUTH_REFRESH_TOKEN"
)

say() { printf '\n=== %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1" >&2; exit 1; }

command -v gcloud >/dev/null || fail "gcloud is not installed. Run this from Cloud Shell."
[ -n "$PROJECT_ID" ] || fail "No project set. Run: gcloud config set project <PROJECT_ID>"

RUNNER="${RUNNER_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
printf 'project: %s\nregion:  %s\nservice: %s\nrunner:  %s\n' \
  "$PROJECT_ID" "$REGION" "$SERVICE" "$RUNNER"

say "Enabling the APIs the deployment needs"
gcloud services enable secretmanager.googleapis.com run.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com --project "$PROJECT_ID"

say "Ensuring the runtime service account exists"
gcloud iam service-accounts describe "$RUNNER" --project "$PROJECT_ID" >/dev/null 2>&1 ||
  gcloud iam service-accounts create "$RUNNER_NAME" --project "$PROJECT_ID" \
    --display-name="MedSemiotics backend runtime"

say "Granting the build account permission to build from source"
BUILDER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$BUILDER" --role="roles/cloudbuild.builds.builder" \
  --condition=None --quiet >/dev/null

# Create a secret if absent; grant the runtime account read access either way.
ensure_secret() {
  local name="$1"
  gcloud secrets describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1 ||
    gcloud secrets create "$name" --replication-policy=automatic --project "$PROJECT_ID" >/dev/null
  gcloud secrets add-iam-policy-binding "$name" --project "$PROJECT_ID" \
    --member="serviceAccount:$RUNNER" --role="roles/secretmanager.secretAccessor" \
    --condition=None --quiet >/dev/null
}

say "Ensuring the backend token exists"
ensure_secret "$TOKEN_SECRET"
if ! gcloud secrets versions list "$TOKEN_SECRET" --project "$PROJECT_ID" --limit=1 \
     --format='value(name)' | grep -q .; then
  openssl rand -hex 32 | gcloud secrets versions add "$TOKEN_SECRET" \
    --project "$PROJECT_ID" --data-file=- >/dev/null
  echo "generated a new backend token"
else
  echo "keeping the existing backend token"
fi

MOUNTS="MEDSEMIOTICS_API_TOKEN=${TOKEN_SECRET}:latest"

say "Checking for a Calendar credential"
if [ -f "$ADC_FILE" ] && python3 -c "
import json,sys
data=json.load(open('$ADC_FILE'))
sys.exit(0 if data.get('refresh_token') and data.get('client_id') else 1)
" 2>/dev/null; then
  for entry in "${CALENDAR_SECRETS[@]}"; do
    name="${entry%%:*}"; rest="${entry#*:}"; key="${rest%%:*}"; env_var="${rest#*:}"
    ensure_secret "$name"
    python3 -c "import json;print(json.load(open('$ADC_FILE'))['$key'],end='')" |
      gcloud secrets versions add "$name" --project "$PROJECT_ID" --data-file=- >/dev/null
    MOUNTS="${MOUNTS},${env_var}=${name}:latest"
  done
  echo "mounted the Calendar credential; the reconciled schedule and the brief will be served"
else
  echo "no Calendar credential found; those two contracts will answer 503 naming what is missing"
fi

say "Deploying"
gcloud run deploy "$SERVICE" --source . --project "$PROJECT_ID" --region "$REGION" \
  --service-account="$RUNNER" --set-secrets "$MOUNTS" --quiet

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" \
  --format='value(status.url)')"
TOKEN="$(gcloud secrets versions access latest --secret="$TOKEN_SECRET" --project "$PROJECT_ID")"
IDENTITY="$(gcloud auth print-identity-token)"

say "Verifying both authorization layers"
check() {
  printf '%-34s %s\n' "$1" "$(curl -s -o /dev/null -w '%{http_code}' "${@:2}")"
}
check "both credentials (expect 200)" -H "Authorization: Bearer $IDENTITY" \
  -H "X-MedSemiotics-Token: $TOKEN" "$URL/v1/semester"
check "no backend token (expect 401)" -H "Authorization: Bearer $IDENTITY" "$URL/v1/semester"
check "no platform identity (expect 403)" -H "X-MedSemiotics-Token: $TOKEN" "$URL/v1/semester"
check "brief for NEURO (200 or 503)" -H "Authorization: Bearer $IDENTITY" \
  -H "X-MedSemiotics-Token: $TOKEN" "$URL/v1/courses/NEURO/brief"

say "Ready"
cat <<EOF
Service URL: $URL

To query it from this shell or a conversational surface:

  export MEDSEMIOTICS_API_BASE_URL=$URL
  export MEDSEMIOTICS_API_TOKEN=\$(gcloud secrets versions access latest --secret=$TOKEN_SECRET)
  export MEDSEMIOTICS_API_IDENTITY_TOKEN=\$(gcloud auth print-identity-token)
  python scripts/backend_query.py /v1/courses/NEURO/next-topic

The identity token expires within the hour; re-export that last one when it does.
EOF
