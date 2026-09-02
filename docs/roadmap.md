# MedSemiotics Copilot master roadmap

This file is the authoritative public product map. MedSemiotics has exactly ten master loops.
Engineering loops such as `0.5F` and `0.6B` are bounded delivery increments mapped to those
master outcomes; they are not additional product loops.

## Ten master loops

| Master loop | Status | Product outcome |
|---|---|---|
| 1. Secure foundation | Complete | Public repository, semester/course configuration, deterministic contracts, privacy boundaries, and audit-ready development workflow. |
| 2. Academic memory | Core complete | Planned syllabus, actual teaching log, covered and pending topics, and rebuildable longitudinal state for NEURO and GASTRO. Classroom-managed Drive structure remains structurally read-only. |
| 3. Coordination and Calendar | Complete and live verified | Effective schedule, Calendar read/reconciliation, and idempotent single-session publishing with named approval for both courses. |
| 4. Teaching Coach and Four C's | Complete through `0.5F` | Coordination, Creativity, Clarity, and Coaching capabilities; curated guides; automatic current-topic selection; human-reviewable preview; separately approved publication. |
| 5. Google Workspace and Classroom | In progress | Persistent dedicated-Workspace authorization, metadata-only course discovery, private provider-neutral snapshots, and a coordinated read view with Calendar and academic state. |
| 6. Assignments, rubrics, and Classroom actions | In progress through `0.7D` | Reviewable assignment/rubric drafts and folder-backed learning materials followed by explicit, persistently idempotent, one-action-at-a-time Classroom execution. No bulk writes or grade publication. |
| 7. PowerSemiotics knowledge and evidence graph | Pending | Topic/class/task links to PowerSemiotics URLs, PMID, DOI, PubMed/Crossref verification, provenance, and source freshness. |
| 8. Creative studio and publishing | Pending | Wikimedia Commons licensing and attribution, audiovisual material, textbook/e-course assets, and review-before-publish PowerSemiotics authoring. |
| 9. Assessment and pedagogical intelligence | Pending | Aggregates, competency performance, item and rubric analytics, validity, reliability, longitudinal student trends, and teaching-performance reflection. |
| 10. Secure cloud mobile orchestrator | Read contracts live verified through `0.8G` | ChatGPT Work as the primary mobile interface, Claude Cowork as an alternative, Codex Cloud and Claude Code web for development, and one provider-neutral MedSemiotics backend. |

## Engineering-loop mapping

| Engineering increments | Master-loop contribution |
|---|---|
| `0.1`-`0.3` | Master loops 1-2 |
| `0.4`-`0.4E` | Master loop 3 |
| `0.5A`-`0.5F` | Master loop 4 |
| `0.6A`-`0.6D` | Master loop 5 |
| `0.6E`-`0.6F` and later bounded actions | Master loop 6 |
| `0.7A` and later assignment/rubric increments | Master loop 6 |
| `0.8A` and later backend-contract increments | Master loop 10 |

Commit `ae3b4e1` enabled public NEURO/GASTRO schedules, Calendar bindings, teaching-guide
catalogs, and cloud-agent safety documentation. It is cross-cutting enablement, not completion of
master loops 5-10.

## Current Google Workspace and Classroom sequence

| Increment | Status | Bounded outcome |
|---|---|---|
| `0.6A` | Complete | Classroom capability, privacy, accountability, OAuth-scope, and data-minimization contract. |
| `0.6B` | Complete | Persistent Apps Script read boundary and metadata-only course discovery. |
| `0.6C` | Complete | Provider-neutral private Classroom snapshot models and normalization. |
| `0.6D` | Complete | Coordination view across Classroom, Calendar, syllabus, and teaching state. |
| `0.6E` | Complete | Explicitly approved, idempotent single Classroom action plan; no grades or bulk writes. |
| `0.6F` | Complete | Authenticated unattended invocation of the Apps Script deployment, live read verification, and one narrowly controlled coursework-draft write with redacted audit evidence. |

## Current assignments and rubrics sequence

| Increment | Status | Bounded outcome |
|---|---|---|
| `0.7A` | Complete | Public NEURO/GASTRO assignment and qualitative-rubric catalogs, syllabus alignment, and one reviewable catalog-backed Classroom draft plan. |
| `0.7B` | Complete | Private atomic applied-action ledger and a rerunnable operator workflow that makes a repeated plan a local no-op before Google is contacted. |
| `0.7C` | Complete in code | Mobile-ready package of one Drive folder plus reviewed PDF, PPTX, Docs, Sheets, Google Forms, or URL links; named content-bound approval and one student-visible `CourseWorkMaterial` using only `classroom.courseworkmaterials`. |
| `0.7D` | Live deployment and controlled publication verified; backend POST pending on `0.7E` configuration | Owner-only Apps Script deployed and authorized; metadata-only discovery matched both courses; one student-visible technical material posted per course; four ledger-backed repeats made no Google request. The materials were posted through the teacher UI, so the owner-only backend POST caller remains to be configured. |
| `0.7E` | Complete in code | Owner-authorized caller for the unattended POST path, held by a secret store (environment or mounted secret-manager volume) instead of a domain-wide delegation grant, with a one-time consent script and fail-closed channel selection. |

## Current mobile backend sequence

| Increment | Status | Bounded outcome |
|---|---|---|
| `0.8A` | Complete and live verified | Read-only backend contracts for semester, course state, next required topic with its curated guide, and one guide by id; bearer-token access from the secret store, fail-closed when unconfigured; no Google credential, no writes, no student data. |
| `0.8B` | Complete and live verified | Coordination view and planned baseline schedule over the same read-only contract, each labelled with what it did and did not consult; Classroom bindings report `not_read` because the backend holds no Google credential. |
| `0.8C` | Complete in code; live verification pending a Calendar credential | Calendar-reconciled effective schedule over the same contract, read with a secret-store credential fixed to `calendar.readonly` and separate from the Classroom caller; an unconfigured backend answers 503 naming the secrets and the planned-baseline endpoint. |
| `0.8D` | Complete in code; live verification pending a Calendar credential | Class brief with automatic topic selection from the reconciled schedule and tracked state, always marked a draft and produced by a chain with no publish path. |
| `0.8E` | Complete and live verified | Deployed surface: the API schema guarded by the same token as the data with the browser doc pages disabled, a GET-only client and operator script that keep the token out of every message, and a Cloud Run runbook plus the documented path for how Cowork or ChatGPT Work consume the contract. |
| `0.8F` | Complete and live verified | Backend token carried in its own header so a platform that authenticates callers keeps `Authorization`, with the dedicated header preferred and both layers applying independently. |
| `0.8G` | Complete and live verified | Application configured before the first request, fixing a cold container that reported itself unconfigured while holding the mounted secret; idempotent fallback for runners that skip the lifespan. |
| `0.8H` | Complete in code | One idempotent operator script that provisions, deploys and verifies the backend, mounting the Calendar credential when the operator has authorized one and reporting its absence when not. |
| `0.9A` | Complete | The official syllabi v2 became the single source of truth: schedules, topic plans and teaching logs are generated from them, guides follow the syllabus in force, and the tests assert the projection instead of restating teaching content. |
| `0.9B` | Complete | Local-only operation after the hosted deployment was retired: the backend still refuses to serve without a token, and the Classroom tooling builds reviewable drafts instead of reporting simulated publications. |
| `0.9C` | Complete | The architecture this project proved is written down for reuse: the principles that transfer, the assumptions that are the author's timetable rather than the method, and a ready-to-copy engineering contract for the clinical platform. |

## Cross-cutting operating contract

- NEURO and GASTRO are equal first-class courses in schedules, Calendar, catalogs, and future
  Classroom operations.
- The public repository contains code, documentation, schemas, and reviewed public catalogs only.
- OAuth credentials, tokens, student identifiers, rosters, submissions, grades, and private
  institutional content remain outside Git in Google Workspace or a runtime secret store.
- Classroom-created Drive folders are never renamed, moved, or reorganized by MedSemiotics.
- Workspace authorization is persistent between runs through the dedicated account, subject to
  Google revocation or scope changes, and always uses the minimum scope for the active increment.
- ChatGPT Work and Claude Cowork never receive unrestricted Google credentials. Both consume the
  same minimized backend contracts.
- Autonomy progresses per capability: observe, recommend, draft, execute with approval, and only
  then narrowly trusted automation.
- The product is cloud- and mobile-first; a packaged desktop executable is not a requirement.
- Product LLM APIs are optional. Deterministic behavior and subscription-based conversational
  surfaces remain usable without runtime OpenAI or Anthropic API billing.
