# Google Calendar Live Integration & Developer Setup

This guide documents the setup, authentication, and controlled smoke testing procedures for Google Calendar integration in MedSemiotics Teaching Copilot.

---

## 1. Prerequisites: Google Cloud OAuth 2.0 Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select your Google Cloud project.
3. Enable the **Google Calendar API** under **APIs & Services > Library**.
4. Configure the **OAuth consent screen**:
   - User Type: **External** (or Internal for Google Workspace domain).
   - Add Test Users: Add your personal Google account email.
5. Create OAuth Client ID:
   - Application Type: **Desktop app**.
   - Name: `MedSemiotics Local Dev`.
6. Download the client secrets JSON file (e.g. `client_secrets.json`).

> [!CAUTION]
> **Security Invariant**: Never commit `client_secrets.json`, `credentials.json`, or cached `token.json` files to Git. Verify that `.gitignore` ignores all credential and token patterns before proceeding.

---

## 2. Local Environment Configuration

Copy `.env.example` to `.env` (ignored by Git) and configure absolute paths to your OAuth files:

```bash
# In .env (or exported in shell environment)
GOOGLE_CALENDAR_CREDENTIALS_FILE="C:/path/to/your/client_secrets.json"
GOOGLE_CALENDAR_TOKEN_FILE="C:/path/to/your/token.json"
```

If separate tokens are desired for read and write scopes, you can point `GOOGLE_CALENDAR_TOKEN_FILE` to distinct cache locations per flow.

---

## 3. Step-by-Step Live Verification Workflow

### Step A: Read-Only Authorization & Calendar Discovery

Run the interactive read smoke script:

```bash
uv run python scripts/google_calendar_smoke.py
```

1. A local browser window will open requesting read-only access (`https://www.googleapis.com/auth/calendar.readonly`).
2. Authorize with your intended Google account.
3. The script will output all accessible calendars (IDs, display names, primary flags) and list events in the primary calendar for the next 7 days.
4. Note down the `calendar_id` of the calendar you wish to use for MedSemiotics teaching events.

### Step B: Controlled Write Authorization & Dry Run

Run the write smoke script in **Dry-Run mode** (default):

```bash
uv run python scripts/google_calendar_write_smoke.py \
  --calendar-id "<YOUR_CALENDAR_ID>" \
  --semester-id "2026-2" \
  --course-code "TEST" \
  --date "2026-09-01" \
  --topic-title "Calendar Integration Test"
```

- Verify that the title, start/end times, and ownership metadata (`medsemiotics_managed="true"`, `medsemiotics_schema_version="1"`, `medsemiotics_course_code="TEST"`) are displayed properly.
- No network mutation is performed in dry-run mode.

### Step C: Execute Live Create Test

To perform the actual write against Google Calendar, add `--execute`:

```bash
uv run python scripts/google_calendar_write_smoke.py \
  --calendar-id "<YOUR_CALENDAR_ID>" \
  --semester-id "2026-2" \
  --course-code "TEST" \
  --date "2026-09-01" \
  --topic-title "Calendar Integration Test" \
  --execute
```

1. A browser window will open requesting event write scope (`https://www.googleapis.com/auth/calendar.events`).
2. Authorize the application.
3. Expected output:
   ```text
   >>> PUBLISH SUCCESSFUL <<<
   Action   : created
   Event ID : <google_event_id>
   ```

### Step D: Execute Live Update Test

Run the script again with a modified `--topic-title` or description content:

```bash
uv run python scripts/google_calendar_write_smoke.py \
  --calendar-id "<YOUR_CALENDAR_ID>" \
  --semester-id "2026-2" \
  --course-code "TEST" \
  --date "2026-09-01" \
  --topic-title "Calendar Integration Test (Updated)" \
  --execute
```

- Expected output: `Action : updated` with the **same** Event ID.

### Step E: Execute Live Unchanged Test

Run the exact same command without changes:

```bash
uv run python scripts/google_calendar_write_smoke.py \
  --calendar-id "<YOUR_CALENDAR_ID>" \
  --semester-id "2026-2" \
  --course-code "TEST" \
  --date "2026-09-01" \
  --topic-title "Calendar Integration Test (Updated)" \
  --execute
```

- Expected output: `Action : unchanged` with zero patch/insert API calls issued.

---

## 4. Safety & Clean-Up Policy

- **No Automated Deletion**: MedSemiotics deliberately does not implement `events.delete()` to prevent destructive data loss.
- **Harmless Test Events**: All smoke test events use `course_code="TEST"` and clearly designated test dates so real academic data is never polluted.
- **Manual Cleanup**: Operators may manually delete the test event directly in Google Calendar UI if desired.
- **Enabled Dedicated Calendars**: NEURO and GASTRO are mapped to dedicated Google Workspace teaching calendars. Calendar IDs are public routing identifiers; OAuth credentials and tokens remain ignored local secrets.
