# Loop 0.7C — controlled Classroom material packages

## Outcome

Loop 0.7C introduces a separate capability for posting reviewed learning materials to students.
It does not widen the assignment writer. One package represents exactly one Google Classroom
`CourseWorkMaterial` containing:

- one required Google Drive folder URL;
- up to nineteen additional reviewed PDF, PPTX, Google Docs, Google Sheets, or web URLs;
- one title and optional description;
- one tracked semester, course, and syllabus topic;
- one named approval bound to the exact visible content and ordered resource list.

Google's API accepts at most twenty materials and uses
`https://www.googleapis.com/auth/classroom.courseworkmaterials` for creation. Links can be upgraded
by Classroom to a more appropriate Drive or media attachment. See the official
[create method](https://developers.google.com/workspace/classroom/reference/rest/v1/courses.courseWorkMaterials/create),
[CourseWorkMaterial resource](https://developers.google.com/workspace/classroom/reference/rest/v1/courses.courseWorkMaterials),
and [Material types](https://developers.google.com/workspace/classroom/reference/rest/v1/Material).

## Mobile and cloud flow

```text
ChatGPT Work / Claude Cowork
    creates or selects a faculty Drive folder
    gathers reviewed resource URLs
                 |
                 v
ClassroomMaterialPackagePlan
    validates HTTPS links, uniqueness, and the 20-item limit
                 |
                 v
faculty preview + named approval of the exact fingerprint
                 |
                 v
private ledger check ---- already applied ---> local no-op
                 |
                 v
exact classroom.courseworkmaterials policy
                 |
                 v
one PUBLISHED CourseWorkMaterial for all students
                 |
                 v
atomic private ledger append
```

The Drive folder is created or organized through the connected Google Drive surface used by the
mobile agent. The MedSemiotics backend receives the resulting HTTPS URL and never receives general
Drive authority. This keeps the product compatible with subscription-based ChatGPT Work and Claude
Cowork workflows without adding a broad Drive API integration to the backend.

## Safety boundaries

- Publication is student-visible and therefore requires `EXECUTE_WITH_APPROVAL`; it is not eligible
  for trusted automation.
- The named approval covers title, description, folder URL, and every resource type/title/URL.
- Editing any visible content changes the fingerprint and forces a new review.
- The package always targets the whole course. Student identifiers and individual assignment modes
  are not representable.
- The backend and Apps Script both enforce one folder plus at most nineteen resources.
- All URLs must be absolute HTTPS links without embedded credentials and must be unique.
- Apps Script fixes the provider state to `PUBLISHED`; callers cannot choose or override it.
- No roster, submission, grade, assignment, update, delete, or bulk operation is exposed.
- The existing private action ledger makes an identical repeat a no-op across process restarts.

## Deployment status

The Python contract, authorization policy, writer, reference Apps Script route, manifest scope, and
hermetic tests are complete. The production Apps Script deployment has **not** been changed by this
commit. Loop 0.7D must:

1. replace the deployed Apps Script with the reviewed reference version;
2. grant the dedicated Workspace account the new `classroom.courseworkmaterials` scope;
3. deploy a new web-app version while retaining owner-only access;
4. run a controlled NEURO draft folder/material package and verify student visibility with no grade
   or individual targeting fields;
5. repeat the identical request with the private ledger and prove that no second Google request is
   made;
6. repeat once for GASTRO.

## Exit criteria

- folder plus URL/PDF/PPTX/Docs/Sheets package contract;
- official twenty-material limit enforced in domain and Apps Script;
- exact content-bound named approval and persistent idempotency;
- exact `classroom.courseworkmaterials` scope and no broader Google authority;
- one explicit `PUBLISHED` result, no student targeting, grades, batch, update, or delete;
- full pytest, Ruff, formatting, strict mypy, and public CI pass.
