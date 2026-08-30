# MedSemiotics Teaching Copilot

**MedSemiotics Teaching Copilot** is an AI-assisted academic teaching and content-management platform for Neurology and Gastroenterology.

> [!CAUTION]
> **Privacy and Data Protection**: Student-identifiable data (names, IDs, emails, grades, submissions, or identifiable work) must **NEVER** be committed to Git. All production datasets, student records, and credential tokens are strictly ignored via `.gitignore`.

---

## Architectural Principles

The platform is structured around the strict conceptual separation of three operational layers:

- **KNOW** (Domain Data & State): Academic state, course syllabi, teaching logs, assignments, medical evidence references, and media metadata.
- **REASON** (Agents, Analytics & Inference): Agentic analysis, psychometrics, pedagogical analytics, and recommendation logic.
- **ACT** (External Actions & Side Effects): Publishing, Google Classroom writes, Google Drive writes, and grading operations. **ACT actions require explicit authorization and are never coupled directly to reasoning logic.**

For details, refer to [ARCHITECTURE.md](ARCHITECTURE.md).

### Four-C Agent Capability Framework

Loop 0.5A defines four bounded agent profiles—**Coordination, Creativity, Clarity, and
Coaching**—and a deterministic autonomy policy:

```text
OBSERVE → RECOMMEND → DRAFT → EXECUTE WITH APPROVAL → TRUSTED AUTOMATION
```

Each capability declares its job, permitted tools, required categories, output, and safety
boundary. The framework produces an auditable allow/deny decision only; it contains no LLM
integration and performs no external action. Calendar writes remain at **execute with approval**
and are not eligible for trusted automation.

#### Teaching Coach draft workflow

`TeachingCoachAgent` prepares a reviewable `CoachingBrief` for one explicit class date by
combining reviewed teaching guidance with the derived course state and effective teaching
position. It rejects inactive dates, cross-course state, and a guide that does not match the
current topic. The agent is deterministic, uses no LLM, and has no Calendar writer; publication
remains a separate explicitly approved action.

`TeachingCoachWorkflow` implements that separate action. It accepts only a coherent draft with
an allowed `coaching.class-brief` DRAFT decision, requires a named human approval for
`coaching.calendar-brief-publish`, and then delegates to the existing Calendar service. The
Calendar service still enforces its own authorization, course configuration, and event-ownership
checks; trusted automation cannot bypass the approval step.

Reviewable source content is stored separately under `config/teaching_guides/`. Catalogs
are validated by semester, course, activation state, and unique topic ID before a guide can reach
the Teaching Coach. NEURO and GASTRO each contain five active public baseline guides aligned with
their tracked syllabus topics. Every Calendar publication remains a separate named human approval.

`CuratedTeachingCoachService` is the read-only entry point for catalog-backed drafting. Its
request identifies the semester, course, class date, and topic; the service loads only that
enabled reviewed guide and delegates to `TeachingCoachAgent`. Disabled or missing content fails
before the agent runs, and the agent still verifies that the selected topic is the effective
topic for the class date. This path exposes no publish operation.

Loop 0.5F adds the usable preview boundary on top of that explicit service.
`TeachingCoachPreviewService` accepts only semester, course, class date, evaluation window, and
requester. It derives the current topic from the effective teaching position, loads the matching
curated guide, asks the existing agent to revalidate and draft, and returns a human-readable title
and body. The preview service has no Calendar writer, publication method, LLM, or caller-selected
topic override.

---

## Technical Baseline

- **Language**: Python 3.12+
- **API Framework**: FastAPI
- **Data Validation**: Pydantic v2
- **Configuration**: YAML / Pydantic Settings
- **Package Management**: `uv`
- **Linting & Formatting**: `ruff`
- **Type Checking**: `mypy` (strict mode)
- **Testing**: `pytest` + `pytest-cov`

---

## Project Structure

```
medsemiotics-teaching-copilot/
│
├── src/
│   └── medsemiotics/
│       ├── __init__.py
│       ├── domain/            # KNOW: Data models and domain entities
│       ├── services/          # Business logic and domain services
│       ├── agents/            # REASON: Pedagogical and reasoning agents
│       ├── integrations/      # External service connectors
│       └── api/               # FastAPI endpoints (GET /health)
│
├── tests/                     # Test suite
├── config/
│   └── semesters/             # Semester configuration YAML files
├── docs/                      # Technical documentation
├── scripts/                   # Utility and maintenance scripts
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
└── CONTRIBUTING.md
```

---

## Semester Configuration

- **Semester Files**: Individual semester definitions are located under `config/semesters/` (e.g. `config/semesters/2026-2.yaml`).
- **Active Semester Pointer**: `config/current_semester.yaml` points to the active semester ID without duplicating configuration.
- **Local State**: Semester configuration is stored as pure, validated local YAML files within the repository.
- **Integration Decoupling**: External integrations (such as Google Drive folders or Classroom sync) are intentionally separated and not part of this domain configuration layer.

---

## Academic State: Planned Curriculum vs. Actual Teaching History

The platform enforces a strict domain distinction between two independent sources of truth:

- **`SyllabusPlan` (Intended Teaching Sequence)**: Models what the official course syllabus intends to teach, in what sequential order (`planned_order`), and target week (`planned_week`).
- **`TeachingSession` (Actual Teaching History)**: Models historical reality—what was actually delivered in a specific classroom/clinical session, the date, session sequence, and topic coverage status (`CoverageStatus`: introduced, partial, completed, reviewed, skipped).

> [!IMPORTANT]
> `SyllabusPlan` and `TeachingSession` **must never be treated as equivalent**. A topic may be planned and never taught, taught across multiple sessions, partially delivered, reviewed, or taught out of the planned order.

---

## Academic State Projection

Academic state is derived through pure, deterministic domain projection rather than AI inference or probabilistic scoring:

$$\text{SyllabusPlan} + \text{TeachingSession history} \longrightarrow \text{CourseAcademicState}$$

The projection engine explicitly distinguishes:
- **Planned Topics**: Defined sequentially in `SyllabusPlan` with mandatory/elective flags.
- **Taught Progress (`TopicProgress`)**: Tracks `session_count`, `first_taught_date`, `last_taught_date`, and status (`not_started`, `in_progress`, `completed`, `skipped`).
- **Completed as Terminal**: Once a topic reaches `completed` in historical sessions, later events cannot regress its completion status.
- **Skipped Topics**: Retained explicitly as `skipped` rather than ignored, so pedagogical reviews can evaluate remediation.
- **Unplanned Taught Content**: Real-world lectures often introduce impromptu clinical topics not in the syllabus; the projector isolates these via `find_unplanned_taught_topic_ids()` without polluting the formal syllabus model.

---

## Teaching Schedule and Position

The platform combines course meeting rules with syllabus and actual teaching history to resolve pacing for any explicit reference date:

$$\text{Schedule} + \text{Syllabus} + \text{Teaching History} + \text{Target Date} \longrightarrow \text{TeachingPosition}$$

- **`CourseTeachingSchedule`**: Defines term boundaries (`teaching_start_date` .. `teaching_end_date`), recurring weekly meeting rules (`ClassMeetingRule`), and overrides (`ScheduleException`: `cancelled`, `no_class`, `makeup`).
- **`TeachingPosition`**: Evaluates whether the target date is a class date, computes `expected_session_count`, `actual_session_count`, `expected_topic_order`, `current_topic_id`, and pacing assessment (`TeachingPaceStatus`: `ahead`, `on_track`, `behind`, `not_started`, `complete`, `unavailable`).
- **Active Date-Only Schedules**: NEURO uses Tuesday/Thursday and GASTRO Monday/Wednesday from 2026-08-01 through 2026-12-15. Exact times and operational exceptions remain Calendar evidence.
- **Deterministic Date Invariant**: All date calculations require an explicit `target_date` argument. No service silently queries the system clock (`date.today()` or `datetime.now()`).

---

## Google Calendar Integration (Read Boundary)

External Google Calendar events are ingested via the narrowest read-only OAuth 2.0 scope (`https://www.googleapis.com/auth/calendar.readonly`):

$$\text{Google Calendar API Resource} \xrightarrow{\text{Mapper}} \text{OperationalCalendarEvent} \xrightarrow{\text{Alias Filter}} \text{Course Events}$$

- **Boundary Isolation**: Raw Google API dictionary structures are strictly mapped into immutable domain models (`OperationalCalendarEvent`, `CalendarDescriptor`). Provider schemas never leak into core services.
- **Timezone Awareness**: All mapped calendar events enforce timezone-aware `datetime` objects. All-day events with exclusive Google end dates are converted to boundary timestamps via explicit `ZoneInfo`.
- **Baseline Schedule Non-Authority**: Google Calendar events are ingested for operational visibility and course alias filtering; they are **not yet authoritative** over baseline syllabus schedules.
- **Separated Capability Invariant**: The reader never receives write scope or exposes write operations. Controlled publishing uses a separate writer, token, authorization gate, and `calendar.events` scope; deletion remains unavailable.
- **Developer Smoke Tool**: An interactive CLI tool [`scripts/google_calendar_smoke.py`](scripts/google_calendar_smoke.py) is available for local verification without impacting automated test suites.

---

## Effective Teaching Schedule

The effective teaching schedule deterministically reconciles institutional planned baseline schedules with operational Google Calendar evidence:

$$\text{Baseline Schedule} + \text{Operational Google Calendar Events} \longrightarrow \text{EffectiveTeachingSchedule}$$

- **Operational Reconciliation**: Planned meeting rules are combined with observed calendar events to establish the actual active class dates.
- **Calendar Absence Invariant**: The absence of a Google Calendar event **never** implies class cancellation. Unobserved baseline dates remain active scheduled classes (`source=baseline`).
- **Explicit Cancellation Markers**: Operational cancellations require explicit, configured text markers (e.g. `"cancelada"`, `"sin clase"` in `cancellation_markers`) within matched calendar event titles.
- **Deterministic and Unpersisted**: `EffectiveTeachingSchedule` is a pure in-memory projection derived on demand; it is never persisted to disk or written back to baseline schedule YAMLs.

---

## Calendar Coaching Publishing (Controlled Write)

Pedagogical briefings and session materials can be published to Google Calendar as structured, tracked events:

$$\text{EffectiveClassEvent} + \text{CoachingBrief} \xrightarrow{\text{Authorized Plan}} \text{CalendarPublishRequest} \xrightarrow{\text{Writer}} \text{Google Calendar}$$

- **Strict Ownership Invariant**: MedSemiotics only mutates calendar events that it explicitly owns. Ownership is tracked strictly via Google Calendar private extended properties (`medsemiotics_managed="true"`, `medsemiotics_semester_id`, `medsemiotics_course_code`, `medsemiotics_class_date`, `medsemiotics_schema_version`), never inferred from display titles.
- **Explicit Authorization Required**: All write workflows require explicit, auditable authorization (`authorized=True`). Unauthorized calls immediately abort with zero external calls.
- **Idempotent Mutation Semantics**:
  - **`created`**: Inserts a new event if no owned event exists for that course and date.
  - **`updated`**: Patches owned fields (`summary`, `description`, `start`, `end`, `location`, `reminders`, `extendedProperties`) if changes are detected. Unrelated fields (attendees, conferenceData, colors) are preserved.
  - **`unchanged`**: Skips API mutations entirely if the existing owned event is already identical.
- **No Destructive Actions**: Event deletions (`events.delete`) are intentionally not implemented.
- **No Bulk Publishing**: Publishing operates strictly on one class session at a time to prevent accidental mass mutations.
- **Minimal Write Scope**: Uses `https://www.googleapis.com/auth/calendar.events` (narrower than full calendar access).
- **Developer Write Smoke Tool**: [`scripts/google_calendar_write_smoke.py`](scripts/google_calendar_write_smoke.py) runs in dry-run mode by default and requires `--execute` for live testing.

---

## Live Calendar Setup

For interactive authentication and controlled live integration testing against real Google Calendars:

1. **OAuth Credentials**: Obtain a Desktop application client secrets JSON file from Google Cloud Console.
2. **Environment Configuration**: Set `GOOGLE_CALENDAR_CREDENTIALS_FILE` and `GOOGLE_CALENDAR_TOKEN_FILE` in your `.env` file (never commit credentials or token files).
3. **Authorize Read Access**: Run `python scripts/google_calendar_smoke.py` to list accessible calendars.
4. **Authorize Write Access**: Run `python scripts/google_calendar_write_smoke.py --calendar-id <ID> --execute` to test controlled event publishing with dry-run protection and ownership tracking.

For full step-by-step instructions, see [docs/google-calendar-live-setup.md](docs/google-calendar-live-setup.md).

NEURO and GASTRO are bound to dedicated Google Workspace calendars. Their IDs are safe routing
identifiers and grant no access; OAuth credentials and tokens remain local secrets. Both calendars
were empty when enabled, so the date-only institutional baseline remains the source of planned
class dates until operational events are added.

The historical six-step live result is preserved in
[`docs/loop-0.4e-live-verification.md`](docs/loop-0.4e-live-verification.md).

The authoritative loop status and the remaining Google Classroom sequence are recorded in
[`docs/roadmap.md`](docs/roadmap.md). The earlier public course enablement commit is a 0.6
foundation, not evidence that the complete 0.6A–0.6F series has been implemented.

Loop 0.6A adds a fail-closed Classroom access policy before any Google adapter. The only allowed
declaration is metadata-only course discovery using exactly the read-only courses scope. Rosters,
student identifiers, coursework, submissions, grades, broader scopes, and every Classroom
mutation are rejected. See
[`docs/loop-0.6a-classroom-access-contract.md`](docs/loop-0.6a-classroom-access-contract.md).

Loop 0.6B makes that contract executable as a metadata-only course discovery read. The persistent
Classroom authorization lives in a private Apps Script web app owned by the dedicated Workspace
account, so MedSemiotics stores no Classroom OAuth token. `ClassroomCourseDiscoveryService`
authorizes the Coordination `OBSERVE` capability and the Loop 0.6A policy before any read, and
`AppsScriptCourseDiscoveryClient` re-verifies that decision and accepts only the five allowlisted
course metadata fields. Prohibited or unrecognized payload fields, declared mutations, and broader
scopes fail closed. The deployment URL and identifier are environment configuration, never tracked
in Git and never echoed in an error. Loop 0.6B ships the transport protocol and its validation
only; authenticated unattended invocation of the deployment belongs to Loop 0.6F. See
[`docs/loop-0.6b-classroom-apps-script-read-boundary.md`](docs/loop-0.6b-classroom-apps-script-read-boundary.md)
and the reference deployment in `scripts/apps_script/`.

Loop 0.6C normalizes that read into a provider-neutral private snapshot. `ExternalCourse` and
`ExternalCourseSnapshot` describe accessible courses without Google field names, fold display names
into an accent-, case-, and whitespace-insensitive comparison form for later matching, and carry the
original provenance. A snapshot is private runtime state: it is never persisted or published, its
SHA-256 fingerprint detects changes between reads without retaining course content, and only the
redacted `audit_summary()` — provenance, counts, and that fingerprint — is safe to log. See
[`docs/loop-0.6c-classroom-snapshot-normalization.md`](docs/loop-0.6c-classroom-snapshot-normalization.md).

Loop 0.6D composes those pieces into a read-only coordination view. For each active course it
records the Classroom binding, the tracked Calendar binding, the syllabus and teaching-log progress
summary, and an explicit readiness with the gaps that keep it from being ready. Matching uses whole
tokens of the course code, course name, or a configured Calendar alias against the normalized
Classroom name, and reports an ambiguity with its candidates rather than guessing. See
[`docs/loop-0.6d-coordination-view.md`](docs/loop-0.6d-coordination-view.md).

Loop 0.6E adds the contract for a single Classroom write, with no execution adapter. A plan
describes one coursework item in draft state — no grading field, no batch representation — and is
only built for a course the coordination view links decisively. A named approval binds to the exact
content digest a reviewer read, so an edited plan is denied until it is re-reviewed, and idempotency
is decided against MedSemiotics' own ledger of applied actions rather than by widening the Classroom
read scope. See [`docs/loop-0.6e-classroom-action-plan.md`](docs/loop-0.6e-classroom-action-plan.md).

Loop 0.6F delivers the authenticated call path and the live read verification procedure. The
transport sends a bearer token for the dedicated Workspace identity, refuses plaintext URLs, never
follows redirects, and reports every Google refusal — a redirect, a 401 or 403, or a sign-in page
returned with HTTP 200 — as an authentication failure rather than a parse error. Errors carry the
status code and exception class only, never the URL, the token, or a response body.
`scripts/classroom_read_smoke.py` runs one authorized read from the operator's environment and
prints redacted, reproducible evidence: counts, lifecycle totals, and a content fingerprint. See
[`docs/loop-0.6f-live-read-verification.md`](docs/loop-0.6f-live-read-verification.md).

Loop 0.6F also applies one narrowly controlled write: a single coursework item created in `DRAFT`
state from an approved Loop 0.6E plan. Google offers no scope that creates teacher coursework
without also granting grade authority, so the boundary is enforced by construction instead — the
Apps Script deployment holds the scope and exposes exactly one grade-free operation, the policy
grants it only for the `own_coursework_draft` category, the plan cannot express a grade, and the
writer rejects any reply that is not a draft or that carries a grading field. The write returns the
ledger entry that makes a repeat of the same plan a no-op.

Loop 0.7A adds public, faculty-reviewable assignment and qualitative-rubric catalogs under
`config/assignments/`. NEURO and GASTRO each contain five synthetic/deidentified-case tasks aligned
with every tracked syllabus topic. `CatalogClassroomAssignmentService` validates catalog, syllabus,
and coordination scopes, renders the reviewed task and rubric into one existing Classroom
`DRAFT` plan, and stops before approval or execution. No student grade, submission, roster, native
Classroom rubric, or bulk action is represented. See
[`docs/loop-0.7a-assignment-rubric-catalog.md`](docs/loop-0.7a-assignment-rubric-catalog.md).

Loop 0.7B closes the previously manual idempotency gap. `ClassroomActionLedgerRepository` loads
and validates a private versioned JSON ledger, rejects conflicting identities, and persists each
successful applied-action record with an atomic file replacement. The Classroom write smoke tool
now requires `--ledger-file`; on a later invocation it supplies the saved records to the existing
authorizer and returns a local `already_applied` no-op before loading the deployment or contacting
Google. The ledger contains only action identity, external course/reference, timestamp, and
accountable actor; it remains outside tracked public content and contains no roster, submission, or
grade data. See [`docs/loop-0.7b-private-action-ledger.md`](docs/loop-0.7b-private-action-ledger.md).

---

## Cloud Agents and Mixed LLM Providers

The public GitHub repository can be used by hosted engineering agents such as Codex cloud and
Claude Code on the web. `AGENTS.md` and `CLAUDE.md` provide a shared safety and quality contract.

This development workflow is separate from product reasoning. A future product runtime may use
OpenAI and Anthropic APIs behind one provider-neutral boundary while deterministic academic state
remains authoritative. LLMs may enrich a draft; they cannot publish to Calendar. See
[`docs/llm-provider-strategy.md`](docs/llm-provider-strategy.md).

---

## Quickstart & Development

### 1. Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed, along with Python 3.12 or higher.

### 2. Environment Setup

Create and activate a virtual environment, then install dependencies:

```bash
# Create virtual environment with uv
uv venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install project and dev dependencies
uv pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

### 4. Running Quality Checks

```bash
# Run linter & formatter checks
ruff check
ruff format --check

# Run static type analysis
mypy

# Run tests with coverage
pytest
```

---

## Contribution Guidelines

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on code quality, branch workflows, and security practices.
