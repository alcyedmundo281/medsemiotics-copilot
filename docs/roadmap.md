# MedSemiotics Copilot master roadmap

This file is the authoritative public product map. MedSemiotics has exactly ten master loops.
Engineering loops such as `0.5F` and `0.6A` are bounded delivery increments mapped to those
master outcomes; they are not additional product loops.

## Ten master loops

| Master loop | Status | Product outcome |
|---|---|---|
| 1. Secure foundation | Complete | Public repository, semester/course configuration, deterministic contracts, privacy boundaries, and audit-ready development workflow. |
| 2. Academic memory | Core complete | Planned syllabus, actual teaching log, covered and pending topics, and rebuildable longitudinal state for NEURO and GASTRO. Classroom-managed Drive structure remains structurally read-only. |
| 3. Coordination and Calendar | Complete and live verified | Effective schedule, Calendar read/reconciliation, and idempotent single-session publishing with named approval for both courses. |
| 4. Teaching Coach and Four C's | Complete through `0.5F` | Coordination, Creativity, Clarity, and Coaching capabilities; curated guides; automatic current-topic selection; human-reviewable preview; separately approved publication. |
| 5. Google Workspace and Classroom | In progress | Persistent dedicated-Workspace authorization, metadata-only course discovery, private provider-neutral snapshots, and a coordinated read view with Calendar and academic state. |
| 6. Assignments, rubrics, and Classroom actions | Pending | Reviewable assignment/rubric drafts followed by explicit, idempotent, one-action-at-a-time Classroom execution. No initial bulk writes or grade publication. |
| 7. PowerSemiotics knowledge and evidence graph | Pending | Topic/class/task links to PowerSemiotics URLs, PMID, DOI, PubMed/Crossref verification, provenance, and source freshness. |
| 8. Creative studio and publishing | Pending | Wikimedia Commons licensing and attribution, audiovisual material, textbook/e-course assets, and review-before-publish PowerSemiotics authoring. |
| 9. Assessment and pedagogical intelligence | Pending | Aggregates, competency performance, item and rubric analytics, validity, reliability, longitudinal student trends, and teaching-performance reflection. |
| 10. Secure cloud mobile orchestrator | Architecture accepted | ChatGPT Work as the primary mobile interface, Claude Cowork as an alternative, Codex Cloud and Claude Code web for development, and one provider-neutral MedSemiotics backend. |

## Engineering-loop mapping

| Engineering increments | Master-loop contribution |
|---|---|
| `0.1`-`0.3` | Master loops 1-2 |
| `0.4`-`0.4E` | Master loop 3 |
| `0.5A`-`0.5F` | Master loop 4 |
| `0.6A`-`0.6D` | Master loop 5 |
| `0.6E`-`0.6F` and later bounded actions | Master loop 6 |

Commit `ae3b4e1` enabled public NEURO/GASTRO schedules, Calendar bindings, teaching-guide
catalogs, and cloud-agent safety documentation. It is cross-cutting enablement, not completion of
master loops 5-10.

## Current Google Workspace and Classroom sequence

| Increment | Status | Bounded outcome |
|---|---|---|
| `0.6A` | Complete | Classroom capability, privacy, accountability, OAuth-scope, and data-minimization contract. |
| `0.6B` | Next | Persistent Apps Script read boundary and metadata-only course discovery. |
| `0.6C` | Pending | Provider-neutral private Classroom snapshot models and normalization. |
| `0.6D` | Pending | Coordination view across Classroom, Calendar, syllabus, and teaching state. |
| `0.6E` | Pending | Explicitly approved, idempotent single Classroom action plan; no grades or bulk writes. |
| `0.6F` | Pending | Live read verification and narrowly controlled write verification with audit evidence. |

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
