# MedSemiotics Copilot loop roadmap

This file is the authoritative public implementation sequence. A loop is complete only when its
bounded contract, tests, and documentation are tracked. A broad enablement commit does not
implicitly complete later subloops.

## Completed foundation

| Loop | Status | Delivered boundary |
|---|---|---|
| 0.1 | Complete | Semester and course configuration |
| 0.2 | Complete | Syllabus and teaching log separation |
| 0.3 | Complete | Deterministic academic state projection |
| 0.4–0.4E | Complete | Schedule, Calendar read, reconciliation, controlled write, live verification |
| 0.5A | Complete | Four-C capability and autonomy framework |
| 0.5B | Complete | Deterministic Teaching Coach agent |
| 0.5C | Complete | Separate approved publication workflow |
| 0.5D | Complete | Curated teaching guide repository |
| 0.5E | Complete | Catalog-backed explicit-topic drafting |
| 0.5F | Complete | Automatic-topic, human-reviewable Teaching Coach preview |

## 0.6 Google Workspace and Classroom series

Commit `ae3b4e1` enabled NEURO and GASTRO schedules, Calendar bindings, public guide catalogs,
cloud-agent safety files, and mixed-provider documentation. It is classified as **0.6 foundation
enablement**. It did not implement Google Classroom access and therefore did not complete the
following subloops.

| Loop | Status | Planned bounded outcome |
|---|---|---|
| 0.6A | Next | Google Workspace/Classroom capability, privacy, approval, and data-minimization contract |
| 0.6B | Pending | Persistent Apps Script Classroom read boundary and course discovery |
| 0.6C | Pending | Provider-neutral private Classroom snapshot models and normalization |
| 0.6D | Pending | Coordination view across Classroom, Calendar, syllabus, and teaching state |
| 0.6E | Pending | Explicitly approved, idempotent single Classroom action plan; no grades or bulk writes |
| 0.6F | Pending | Live read verification and narrowly controlled write verification with audit evidence |

Student-identifiable data, submissions, grades, OAuth tokens, and private institutional content
must never enter the public repository. Apps Script authorization belongs to the dedicated Google
Workspace account and uses the minimum scopes required by each subloop.

## 0.7 Mobile cloud workspace

0.7 begins only after the read path in 0.6 is stable. ChatGPT Work is the primary mobile
interface, Claude Cowork is the comparison surface, and Codex cloud plus Claude Code on the web
remain development agents. Both conversational surfaces must use the same secure MedSemiotics
state and approval contracts; neither receives direct unrestricted Google credentials.
