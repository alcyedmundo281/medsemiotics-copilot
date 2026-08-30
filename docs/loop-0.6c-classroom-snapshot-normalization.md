# Loop 0.6C: provider-neutral private snapshots

Loop 0.6C turns an authorized Classroom read into a provider-neutral snapshot that the rest of
MedSemiotics can reason about without knowing that Google Classroom exists. It performs no network
request, holds no authorization of its own, and adds no new data category.

## Provider-neutral models

`ExternalCourse` describes one course as `provider`, `external_id`, `display_name`, `section`,
`lifecycle`, and an optional HTTPS `link` — the same non-personal metadata Loop 0.6B allows,
expressed without Google field names. `ExternalCourseLifecycle` replaces the Classroom-specific
course state, and `ExternalCourseProvider` names the platform the data came from, so a second
provider can be added later without reshaping the model.

`ExternalCourseSnapshot` is the point-in-time view: provider, capture timestamp, requester, the
authorized boundary that produced the data (`source_reference`), the approved scopes, and the
courses. Provenance is carried through unchanged from the Loop 0.6B result rather than re-derived.

## Deterministic normalization

`normalize_course_name()` folds a display name into a comparison form: Unicode decomposition,
combining marks removed, whitespace collapsed, case folded. `Semiología   NEUROLÓGICA` and
`semiologia neurologica` therefore share one `normalized_name`, which is what a later increment
will match against academic state — accents and manual spacing differ between platforms and
between edits, and must not decide whether two records are the same course.

The display name is preserved exactly as reported; normalization never overwrites it. Snapshots
order courses by `(normalized_name, external_id)`, reject duplicate provider/identifier pairs, and
require a timezone-aware capture timestamp, so the same read always rebuilds the same snapshot.

Normalization fails closed: a course state with no provider-neutral equivalent, or provider data
that cannot form a valid snapshot, raises `ExternalCourseSnapshotError` instead of degrading into a
partial view.

## Private by construction

A snapshot is private runtime state. It is never written to tracked configuration, never published,
and no repository class persists it.

`ExternalCourseSnapshot.fingerprint` is a SHA-256 digest over the normalized course content, so a
caller can detect that the accessible courses changed — `has_same_content()` — without storing
names, identifiers, or links. `audit_summary()` returns the only projection intended to leave the
process: provider, capture time, `source_reference`, course count, per-lifecycle counts, and the
fingerprint. It carries no course name, identifier, section, or link, and is therefore safe to log
or show to an operator.

Capture metadata is deliberately outside the fingerprint: two reads by different people at
different times of an unchanged Classroom compare equal.

## Explicitly out of scope

- any network request, authorization, or scope of its own — the snapshot is built from a
  `ClassroomCourseDiscovery` that Loop 0.6B already authorized and sanitized;
- binding an external course to a MedSemiotics course code, syllabus, schedule, or Calendar, which
  is the coordinated read view of Loop 0.6D;
- persisting snapshots anywhere;
- rosters, student identifiers, coursework, submissions, grades, and every mutation.

## Exit criteria

- immutable, strict provider-neutral course and snapshot models;
- deterministic accent-, case-, and whitespace-insensitive name normalization;
- exhaustive Classroom lifecycle mapping proven by a test over every course state;
- fingerprint-based change detection that retains no course content;
- a redacted audit summary proven not to carry names, identifiers, sections, or links;
- full pytest, Ruff, and strict mypy quality gates with no network access in tests.
