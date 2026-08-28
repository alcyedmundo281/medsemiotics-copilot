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
- **Academic Domain Entities**: `Course`, `SemesterConfig`, `CourseCode`, and `SemesterId` representing validated academic structures.
- **Semester Configuration Repository & Pointer**: `SemesterRepository` providing pure read-only access to semester definitions on disk, and `current_semester.yaml` holding the active semester pointer.
- **Configuration vs. Integration**: Semester YAML files (`config/semesters/*.yaml`) represent static domain configuration and state, **not** an external integration.
- **Syllabus**: Planned vs. actual taught syllabus tracking, topic hierarchies, competency mappings for Neurology and Gastroenterology.
- **Teaching Logs**: Chronological lecture/seminar logs, instructor notes, clinical vignette associations.
- **Assignments & Rubrics**: Assessment structures, rubric criteria, submission schema definitions.
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

**Rules for REASON**:
- Consumes state from the **KNOW** layer.
- Never directly mutates external platforms (such as Google Classroom, Google Drive, or production databases).
- Emits structured, verifiable **Action Proposals / Intents** rather than executing side effects.

---

## 3. ACT: External Actions & Side Effects

The **ACT** layer executes write actions, mutations, and integrations with external systems.

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
