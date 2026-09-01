# Loop 0.9A — The official syllabus is the source of truth

## Why

Two records of what is taught had drifted apart. The tracked engine configuration said the term
started on 1 August with a twice-weekly NEURO baseline and a reconstructed GASTRO first half,
while the official syllabi committed as `config/syllabi/2026-2/silabo_*_v2.yaml` say the term
started on 23 and 24 June with one weekly class per course and name all eighteen weeks.

An engine that answers "what do I teach next" from the wrong record is worse than no engine. This
increment makes the official syllabi the single source of truth and derives every deterministic
file from them.

## What changed

`scripts/sync_syllabus_v2_to_config.py` projects each official syllabus onto the three files the
engine reads:

| Generated file | Derived from |
|---|---|
| `config/schedules/2026-2/<COURSE>.yaml` | `course_info.start_date`, `course_info.end_date`, and the weekday of the start date |
| `config/syllabi/2026-2/<COURSE>.yaml` | the eighteen weeks, in week order |
| `config/teaching_logs/2026-2/<COURSE>.yaml` | only the weeks marked `completed` |

Each generated file carries a header naming the script and its source, and
`tests/test_real_config.py` fails when a tracked file drifts from the official syllabi.

The resulting state for 2026-2:

| Course | Weekday | Term | Delivered | Next topic |
|---|---|---|---|---|
| NEURO | Tuesday | 2026-06-23 → 2026-10-20 | weeks 1–10 | `trastornos-movimiento-2` (2026-09-01) |
| GASTRO | Wednesday | 2026-06-24 → 2026-10-21 | weeks 1–10 | `colitis-ulcerosa` (2026-09-02) |

## Keeping it current

After teaching a class, mark that week `completed` in the official syllabus and regenerate:

```bash
python scripts/sync_syllabus_v2_to_config.py
```

The next class then becomes the first week that is not `completed`, and the engine proposes it.

## Guides follow the syllabus

A curated guide may only target a topic the course still teaches. Guides for
`trastornos-movimiento-2` and `colitis-ulcerosa` were curated, the pares craneales entries were
retired because syllabus v2 splits that week in two, and
`test_next_topic_of_each_course_has_a_curated_guide` fails when the upcoming class has no guide —
the failure names the guide to write.

## Tests are decoupled from teaching content

`tests/test_real_config.py` now asserts that the tracked configuration is a faithful projection of
the official syllabi, rather than restating topic identifiers. `tests/test_backend_api.py` builds
its own synthetic configuration, so updating what is taught never breaks the API suite.
