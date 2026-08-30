# Loop 0.7A: catalog-backed assignments and qualitative rubrics

Loop 0.7A begins the next delivery series inside master loop 6. It replaces free-text operator
input with faculty-reviewable, versioned assignment and rubric catalogs for NEURO and GASTRO.

## Public baseline

`config/assignments/<semester>/<course>.yaml` now supplies five assignment templates for each
active course, aligned one-to-one with its five tracked syllabus topics. Each course also supplies
one reusable qualitative clinical-reasoning rubric.

An assignment contains a stable identifier, topic, title, reviewed prompt, expected deliverables,
rubric reference, and suggested review interval. A rubric contains qualitative performance levels
and criteria whose relative weights total 100 percent. It contains no student score, grade,
submission, or identifiable work.

All baseline prompts require synthetic or deidentified cases. The rendered Classroom instructions
repeat that privacy boundary explicitly.

## KNOW to ACT-plan flow

```text
assignment/rubric catalog + tracked syllabus       KNOW / read only
                     +
decisive Classroom coordination entry              KNOW / read only
                     |
                     v
CatalogClassroomAssignmentService
                     |
                     v
reviewable ClassroomActionPlan                     ACT proposal only
```

The service validates that the requested course matches the coordination entry, the catalog is
enabled, the assignment's topic exists in the tracked syllabus, and the referenced rubric is
present. It then delegates to the existing `ClassroomActionPlanner`, producing exactly one
coursework item in `DRAFT` state.

The service does not authorize, execute, publish, or grade. A reviewer must inspect the complete
rendered instructions before creating a separate `ClassroomActionApproval`; the existing 0.6E
authorizer and 0.6F writer remain the only path to an external write.

## Explicitly out of scope

- automatic assignment selection without faculty review;
- native Google Classroom rubric creation;
- student-visible publication, grading, points, submissions, or rosters;
- bulk actions;
- a persistent private applied-action ledger;
- live Classroom execution.

## Exit criteria

- strict immutable assignment, rubric, catalog, request, and draft models;
- unique stable identifiers, complete rubric references, and criterion weights totaling 100;
- read-only repository with safe semester/course path resolution;
- ten public baseline tasks covering every tracked NEURO/GASTRO syllabus topic;
- deterministic rendering into one existing Classroom draft plan;
- privacy notice embedded in every rendered plan;
- full pytest, Ruff, formatting, and strict mypy quality gates.
