# Loop 0.6D: coordination view

Loop 0.6D answers one question for each active course: is it actually wired for coordinated
teaching support, and if not, what is missing? It reads tracked configuration, tracked academic
state, and an already-authorized Classroom snapshot. It contacts no provider, holds no scope of its
own, and writes nothing.

## What the view composes

For every active course in the semester, `CourseCoordinationEntry` records:

- **Classroom** — `ClassroomLink`: `linked` with the external id, display name and lifecycle;
  `not_found`; `ambiguous` with the competing candidate ids; or `not_read` when no snapshot was
  supplied. Every outcome carries a reason.
- **Calendar** — `CalendarLink`: `configured` with the bound calendar, `disabled`, or `missing`.
  This is the tracked binding only; no Calendar event is read.
- **Academic state** — `AcademicProgressSummary`: planned topic total, completed, in progress, not
  started, skipped, and the next required topic, derived from the existing syllabus and
  teaching-log projection.
- **Readiness** — `ready` when nothing is missing, `blocked` when no syllabus topics are tracked
  (there is nothing to coordinate), otherwise `partial`. Readiness and blockers are validated
  against each other, so a `ready` entry cannot carry a gap and an unready one cannot hide it.

The view also lists accessible external courses no tracked course claims, and the tracked courses
skipped because they are inactive.

## Matching never guesses

A tracked course claims an external course when the course code, the course name, or a configured
Calendar alias appears in the external display name as a contiguous run of whole tokens, compared
in the Loop 0.6C normalized form (accent-, case-, and whitespace-insensitive). Whole-token matching
is what keeps `NEURO` from claiming `Neurogastroenterología`.

Two outcomes are deliberately non-decisions rather than guesses, and both name the candidates so a
human can resolve them:

- more than one external course matches a tracked course;
- one external course matches more than one tracked course.

Reusing the existing Calendar `aliases` means recognition rules live in one tracked place instead of
a second, divergent list.

## Boundaries

- OBSERVE-only: the new `coordination.course-coordination-view` capability is registered with both
  a minimum and maximum autonomy of OBSERVE and cannot mutate anything.
- No network: the view consumes a `ClassroomCourseDiscovery` already authorized by Loop 0.6B and
  normalized by Loop 0.6C, or no snapshot at all.
- Fail closed on mixed scopes: calendar configuration from another semester, duplicate
  configuration for one course, or academic state projected for another course raises
  `CoordinationViewError` instead of producing a misleading view.
- No student data: the view carries course metadata, counts, and topic identifiers only.

## Explicitly out of scope

- reading or reconciling Calendar events, which the effective-schedule services already own;
- persisting the view or any binding it infers;
- writing a link back to Classroom, Calendar, or tracked configuration;
- assignment or rubric drafts and Classroom actions, which belong to Loop 0.6E;
- rosters, student identifiers, coursework, submissions, and grades.

## Exit criteria

- immutable, strict models whose validators keep every binding, count, and readiness self-consistent;
- deterministic whole-token matching over normalized names, with ambiguity reported both ways;
- explicit reasons and blockers on every non-ready outcome;
- OBSERVE-only capability registration proven by test;
- full pytest, Ruff, and strict mypy quality gates with no network access in tests.
