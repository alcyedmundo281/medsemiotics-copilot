# Architecture: KNOW → REASON → ACT

MedSemiotics Teaching Copilot is designed on a core architectural principle: the strict separation of **KNOW**, **REASON**, and **ACT** layers.

```
┌─────────────────────────────────────────────────────────────┐
│                            KNOW                             │
│     Academic State • Syllabi • Teaching Logs • Evidence     │
└──────────────────────────────┬──────────────────────────────┘
                               │ (reads domain data)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                           REASON                            │
│     Agents • Pedagogical Analytics • Recommendation Logic   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (produces audited action intent)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                            ACT                              │
│   Google Classroom • Drive Writes • Publishing • Grading    │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. KNOW: Domain Data and State

The **KNOW** layer holds the authoritative domain representations, data models, state storage, and invariant rules of the academic environment.

- **Academic State**: Course configurations, semesters, enrollment definitions, grading schemes.
- **Academic Domain Entities**: `Course`, `SemesterConfig`, `Topic`, `CourseCode`, `SemesterId`, and `TopicId` representing validated academic building blocks.
- **Curriculum Planning vs. Teaching Reality**:
  - `SyllabusPlan` & `SyllabusTopic`: The intended sequential curriculum structure (`planned_order`, `planned_week`).
  - `TeachingSession` & `TeachingSessionTopic` (`CoverageStatus`): Historical log of actual class meetings and coverage achieved (`introduced`, `partial`, `completed`, `reviewed`, `skipped`).
  - **Core Invariant**: **"Planned curriculum and actual teaching history are separate sources of truth."**
- **Teaching Schedule and Position**:
  - `CourseTeachingSchedule`, `ClassMeetingRule`, and `ScheduleException` (`ScheduleExceptionType`): Calendar schedule rules and exception days (`cancelled`, `no_class`, `makeup`).
  - `TeachingPosition` (`TeachingPaceStatus`): Point-in-time pacing and topic evaluation (`ahead`, `on_track`, `behind`, `not_started`, `complete`, `unavailable`).
  - `TeachingDayService`: Application service resolving scheduled class days, pacing deltas, and current topics for explicit evaluation dates.
  - **Core Invariant**: **"Date-sensitive academic reasoning must receive an explicit target date."** No service in this layer silently queries `datetime.now()` or `date.today()`.
- **Derived Academic State Projection**:
  - `TopicProgress` (`TopicProgressStatus`): Topic-level progress derived from historical sessions (`session_count`, `first_taught_date`, `last_taught_date`).
  - `CourseAcademicState`: Aggregated deterministic course state exposing filtered progress queries (`completed_topics`, `in_progress_topics`, `not_started_topics`, `skipped_topics`, `next_required_topic`, `completion_ratio`).
  - `CourseStateService`: Read-only orchestration service combining syllabus and log repositories to project current state without persistence.
  - **Core Invariant**: **"Derived academic state can always be rebuilt from syllabus configuration and teaching history."** `CourseAcademicState` is pure in-memory projection and is never stored in static YAML files.
- **Repositories & Storage**:
  - `SemesterRepository`: Read-only access to semester definitions on disk (`config/semesters/`).
  - `SyllabusRepository`: Read-only access to planned syllabi (`config/syllabi/<semester_id>/<course_code>.yaml`).
  - `TeachingLogRepository`: Read-only access to historical teaching sessions (`config/teaching_logs/<semester_id>/<course_code>.yaml`).
  - `ScheduleRepository`: Read-only access to teaching schedules (`config/schedules/<semester_id>/<course_code>.yaml`).
  - `CalendarConfigRepository`: Read-only access to course calendar bindings (`config/calendar/<semester_id>/<course_code>.yaml`).
- **Effective Teaching Schedule & Reconciliation**:
  - `EffectiveClassEvent` (`EffectiveClassSource`: `baseline`, `calendar`, `baseline_and_calendar`; `EffectiveClassStatus`: `scheduled`, `cancelled`, `moved`, `makeup`): Point-in-time reconciled class event.
  - `EffectiveTeachingSchedule`: Derived, unpersisted schedule reconciling planned baseline rules with operational Google Calendar evidence.
  - `EffectiveScheduleService` & `EffectiveTeachingDayService`: Application services computing effective dates, positions, and current topics.
  - **Core Invariant**: **"Baseline schedule is planned truth; Calendar provides operational evidence."** Reconciliation preserves both planned structure and observed reality without mutating either store.
  - **Core Invariant**: **"Absence of external evidence must not silently negate planned academic state."** Unobserved baseline class dates remain active scheduled classes unless an explicit cancellation marker is present.
- **External Integration Boundaries**:
  - `GoogleCalendarReader`: Read-only client for Google Calendar API v3 using user OAuth 2.0 with minimal readonly scope.
  - `OperationalCalendarEvent`: Normalized domain model for external calendar events.
  - `CourseCalendarConfig`: Course-to-calendar binding and title matching aliases.
  - **Core Invariant**: **"External provider models must not cross the integration boundary."** All raw provider schemas are mapped into internal domain models at the integration adapter layer.
  - **Core Invariant**: **"Google Calendar read access and Calendar write access are separate capabilities."** Read ingestion does not imply or grant write authorization.
- **Configuration vs. Integration**: Semester, syllabus, and schedule YAML files represent static domain configuration and state, **not** external integrations.
- **Evidence & Literature**: PubMed, PMC, DOI, and Crossref metadata and citation records.
- **Media & Assets**: Wikimedia Commons media indexing, medical illustrations, attribution records, and licensing metadata.

**Rules for KNOW**:
- Contains immutable schemas and pure domain state models (Pydantic / SQL / YAML).
- Does not execute agentic reasoning or LLM inference.
- Does not perform external mutating operations.
- Purely read-only data access without external network dependencies.

---

## 2. REASON: Agents, Analysis, and Inference

The **REASON** layer contains the intelligence, evaluation algorithms, and agentic workflows that interpret domain data.

- **Specialized Agents**: Conversational teaching copilot, syllabus-matching agents, clinical vignette generators, literature verification agents.
- **Pedagogical Analytics**: Concept drift detection, curriculum coverage gaps, alignment analysis between planned and taught content.
- **Psychometrics & Assessment Analytics**: Item discrimination, distractor efficiency, rubric calibration, difficulty indexing.
- **Recommendation Logic**: Proposing next lecture adjustments, recommending supplementary readings, drafting assignments.

### Agent Capability Framework (Four C's)

The REASON layer declares four specialized agent pillars instead of granting a general-purpose
agent implicit access to every tool:

| Agent | Job | Initial boundary |
|---|---|---|
| **Coordination** | Align academic state, Calendar, tasks, and preparation | Calendar writes require per-action approval |
| **Creativity** | Produce reviewable teaching and publication artifacts | Draft only; no publishing or distribution |
| **Clarity** | Review evidence and assessments at panoramic or item level | Read/recommend only; no grades or medical publishing |
| **Coaching** | Prepare class briefings and pedagogical improvement | Draft first; publishing remains a separate approved ACT step |

Every registered capability explicitly declares **JOB, TOOLS, CATEGORIES, OUTPUT, and
BOUNDARY**. `AgentCapabilityFramework` then evaluates an immutable `AgentActionIntent`
against this contract without invoking an LLM or executing a tool.

Autonomy is progressive and capability-specific:

```text
0 OBSERVE
    ↓
1 RECOMMEND
    ↓
2 DRAFT
    ↓
3 EXECUTE WITH APPROVAL
    ↓
4 TRUSTED AUTOMATION
```

- A capability cannot operate below its declared minimum or above its declared ceiling.
- Every level-3 execution requires explicit approval with an accountable approver.
- Level 4 requires both capability eligibility and a separately enabled narrow automation policy.
- External mutations cannot begin below level 3.
- The Loop 0.5A catalog marks no external mutation as eligible for trusted automation.
- Authorization by this framework does not bypass downstream ACT-layer protections. Calendar
  publishing still requires `authorized=True`, enabled course configuration, and owned-event
  metadata.

**Core Invariant**: **"An agent does not gain autonomy by existing; it gains autonomy only
through an explicit, proven, and auditable policy."**

### Teaching Coach Agent

`TeachingCoachAgent` is the first concrete consumer of the capability framework. It operates
only through `coaching.class-brief` at autonomy level **DRAFT**:

```text
Reviewed TeachingTopicGuide
        + CourseAcademicState
        + effective TeachingPosition for an explicit date
        + authorized DRAFT capability
                    ↓
          TeachingCoachDraftResult
                    └── reviewable CoachingBrief
```

The agent validates semester, course, date, active-class status, and current topic before
composing a brief. Its contextual coaching notes are deterministic and traceable to
`TeachingPaceStatus` and `TopicProgressStatus`; it does not invent medical content. Clinical
objectives, critical points, questions, pitfalls, and materials must come from a curated
`TeachingTopicGuide`.

The agent has no Calendar writer or other mutating dependency. Publishing the resulting draft
remains a separate ACT workflow through `CalendarCoachingService`, the level-3 capability gate,
and the existing `authorized=True` plus event-ownership protections.

### Approved Teaching Coach Workflow

`TeachingCoachWorkflow` preserves a hard review boundary between drafting and publication:

```text
TeachingCoachAgent.draft()                 REASON / level 2
        ↓ reviewed TeachingCoachDraftResult
TeachingCoachWorkflow.publish()
        ├── validates draft provenance and scope
        ├── requires named human approval      level 3
        └── CalendarCoachingService
                ├── authorized=True
                ├── enabled course configuration
                └── owned-event-only mutation  ACT
```

Trusted automation does not satisfy the level-3 approval gate, and no one-call
`draft_and_publish` path exists. A caller must first obtain and review a coherent draft, then
submit a distinct publication request with an `AgentAuthorizationContext` naming the approver.

### Curated Teaching Guide Repository

Clinical and pedagogical source content is loaded through the read-only
`TeachingGuideRepository` from `config/teaching_guides/<semester>/<course>.yaml`. Each
`CourseTeachingGuideCatalog` is scope-validated, rejects duplicate topic IDs, and must contain at
least one complete `TeachingTopicGuide` before it can be enabled.

The tracked NEURO and GASTRO catalogs are enabled public baselines with five guides each, aligned
one-to-one with their tracked syllabus topics. The guides supply reviewable objectives, critical
points, questions, pitfalls, and materials; they do not bypass the separate named approval needed
for Calendar publication.

`CuratedTeachingCoachService` connects this repository to the draft-only agent without crossing
the ACT boundary:

```text
CuratedTeachingCoachDraftRequest
        ↓ explicit semester / course / date / topic
TeachingGuideRepository                 KNOW / read only
        ↓ enabled faculty-authored TeachingTopicGuide
TeachingCoachAgent                      REASON / level 2
        ↓ validates effective topic and course state
TeachingCoachDraftResult                reviewable; never auto-published
```

A disabled or missing catalog stops the flow before reasoning begins. A valid guide still does
not override the effective teaching position: topic mismatch remains a controlled agent error.

### Teaching Coach Preview Boundary

Loop 0.5F removes the need for a conversational or mobile caller to know the internal topic ID:

```text
semester + course + class date + explicit evaluation window
        ↓
TeachingCoachPreviewService
        ├── resolves the effective current topic      KNOW / read only
        ├── loads the enabled curated topic guide     KNOW / read only
        ├── delegates to TeachingCoachAgent           REASON / level 2
        └── formats title + body for human review
```

The agent deliberately revalidates the position after automatic topic selection. If operational
state changes between selection and drafting, the request fails closed instead of rendering a
stale topic. The preview result remains a draft: it contains no approval evidence and cannot call
Calendar, Classroom, Drive, or any other ACT adapter.

### Cloud Engineering Agents vs. Product LLMs

Codex cloud and Claude Code on the web are development environments operating on hosted GitHub
checkouts. They may propose repository changes under `AGENTS.md` and `CLAUDE.md`, but repository
access grants neither Google OAuth credentials nor product runtime authority.

Product LLMs form a separate optional REASON sub-boundary. OpenAI and Anthropic APIs may enrich a
structured draft through a provider-neutral adapter; deterministic academic state, capability
decisions, and ACT authorization remain authoritative. Provider selection never changes Calendar
permissions, and no LLM client may depend directly on a Calendar writer. The detailed contract is
documented in `docs/llm-provider-strategy.md`.

**Rules for REASON**:
- Consumes state from the **KNOW** layer.
- Never directly mutates external platforms (such as Google Classroom, Google Drive, or production databases).
- Emits structured, verifiable **Action Proposals / Intents** rather than executing side effects.

---

## 3. ACT: External Actions & Side Effects

The **ACT** layer executes write actions, mutations, and integrations with external systems.

- **Google Calendar Coaching Publishing**:
  - `CoachingBrief` & `CalendarPublishRequest`: Structured domain models for pedagogical session briefings and provider-neutral write intents.
  - `GoogleCalendarWriter`: External integration client executing controlled creates and patches using `calendar.events` write scope.
  - `CalendarCoachingService`: Service enforcing authorization gates and managing class briefing publications.
  - **Core Invariant**: **"MedSemiotics may mutate only Calendar events it explicitly owns."** Event ownership is identified exclusively via private extended properties (`medsemiotics_*`).
  - **Core Invariant**: **"Ownership must never be inferred from display text."**
  - **Core Invariant**: **"Calendar write operations require explicit authorization."** `authorized=True` is required for any external write call.
- **Google Classroom**: Creating coursework, posting announcements, updating assignments, synchronizing grades.
- **Google Drive**: Reading/writing classroom folders, organizing exported materials, managing backups.
- **Publishing & Distribution**: Exporting semester packages, syndicating syllabus updates to PowerSemiotics.
- **Destructive Actions**: Overwriting files, publishing grades, mass communications.

**Rules for ACT**:
- **Strict Decoupling**: **ACT must never be directly coupled to reasoning logic.**
- **Explicit Authorization**: External writes and state mutations require explicit, auditable authorization gates (human-in-the-loop or policy-based verification).
- **Idempotence & Auditability**: Every external write must be logged with an auditable trail capturing who authorized the action, timestamp, source reasoning intent, and execution status.

---

## Layer Boundary Rules Summary

| Layer | Depends On | Disallowed Behaviors |
|---|---|---|
| **KNOW** | Pure Python standard library & schemas | Must not call LLMs or external APIs |
| **REASON** | **KNOW** | Must not execute mutating write side-effects |
| **ACT** | **KNOW**, explicit authorized intents | Must not contain embedded agent reasoning |
