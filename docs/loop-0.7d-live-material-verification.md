# Loop 0.7D — live Classroom material verification

## Outcome

On 2026-08-30 the dedicated Google Workspace identity completed a controlled live verification of
the Loop 0.7C material contract for both tracked courses.

- A dedicated Apps Script project was created, authorized, and deployed as the Workspace owner.
- The web app is restricted to the owner and executes as that owner.
- Its active manifest enables the Classroom advanced service and declares the existing course-read
  and coursework-draft scopes plus `classroom.courseworkmaterials`.
- A metadata-only web-app request returned four active courses and decisively matched the tracked
  Neurologia and Gastroenterología HECAM courses. No roster, student, submission, or grade data was
  requested or returned.
- One empty technical verification folder was created in the dedicated Drive and shared as
  read-only to anyone with the link, with link discovery disabled.
- Classroom added its own course reader/teacher group permissions when that folder was attached.
- Exactly one technical material was posted to the whole Neurologia course and one to the whole
  Gastroenterología course. Both carried the same reviewed title, description, and folder; neither
  represented grades, submissions, individual targeting, update, delete, or batch execution.
- The two provider references were imported into a private ledger outside Git. Two later
  invocations per course returned a local `already_applied` no-op before deployment configuration
  was loaded, so no repeat contacted Google and no duplicate was created.

No deployment URL, deployment identifier, course identifier, material identifier, Classroom group
address, OAuth token, credential, roster, submission, or grade is recorded in the public repository.

## Reviewed visible package

```text
Title: MedSemiotics Copilot — verificación técnica 0.7D
Description: Verificación controlada del canal de materiales. La carpeta no contiene datos
             estudiantiles ni calificaciones.
Audience: all students in exactly one course
Attachments: one empty Google Drive verification folder
Topic: none
State: student-visible / posted
```

The Drive permission was verified after publication as `anyone: reader` with discovery disabled.
Google also reported course-specific reader and teacher-group permissions; their addresses remain
private.

## Idempotency evidence

The operator tool added in this increment is
[`scripts/classroom_material_publish_smoke.py`](../scripts/classroom_material_publish_smoke.py).
It builds the same content-bound plan used by the Loop 0.7C authorizer, loads the required private
ledger, and handles `already_applied` before loading the deployment or caller credentials.

The live ledger contains two records outside Git. Four repeat executions produced:

```text
NEURO repeat 1: already_applied; no Google request
NEURO repeat 2: already_applied; no Google request
GASTRO repeat 1: already_applied; no Google request
GASTRO repeat 2: already_applied; no Google request
```

The first Windows runs also exposed a console portability defect: CP1252 could not render the
Unicode success marker. The operator output now uses ASCII status prefixes, and a regression test
enforces that constraint.

## Important boundary: unattended POST remains pending

This verification does **not** claim that the private backend POST transport was exercised live.
The owner-only web app was live-tested for metadata discovery, while the two student-visible
materials were posted through the authenticated Classroom teacher interface. Their references were
then recorded in the same private ledger used by the deterministic no-duplicate gate.

The repository's unattended transport requires a separately configured caller identity capable of
invoking an owner-only Workspace web app. No local service-account key or delegated caller was
present, and no new key or domain-wide delegation was created merely to close a test.

> **Loop 0.7E supplies that caller.** Rather than creating a domain-wide delegation grant, the
> deployment owner authorizes the operator application once and the refresh token is held by a
> secret store. See `docs/loop-0.7e-owner-authorized-caller.md` for the channel, the consent
> script, and the steps that close this gap. Until those steps run,
> `AppsScriptCourseworkMaterialWriter.publish` remains hermetically verified but its live POST path
> is not.

## Quality evidence

- full suite before the final console-only fix: 801 passed;
- focused operator regression suite after the fix: 6 passed;
- Ruff: clean;
- strict mypy: clean before the console-only fix;
- no secrets or private institutional identifiers added to Git.

