# MedSemiotics Copilot agent instructions

This repository is public. Never commit credentials, OAuth tokens, API keys, student-identifiable
data, protected health information, private clinical records, or confidential institutional data.

## Engineering contract

- Use Python 3.12 and `uv`.
- Preserve the `KNOW -> REASON -> ACT` boundaries documented in `ARCHITECTURE.md`.
- Keep academic state and schedules deterministic and rebuildable from tracked configuration.
- Treat LLM output as a proposal or draft, never as authoritative academic or clinical state.
- Require explicit, named human approval before any Google Calendar write.
- Do not add Calendar deletion, bulk publishing, grade publication, or autonomous external writes.
- Run pytest, Ruff, and strict mypy before proposing a merge.
- Work on a feature branch and keep changes reviewable.

## Course configuration

NEURO and GASTRO are active for semester `2026-2`. Their tracked schedules are date-only
baselines; Google Calendar supplies operational evidence such as exact event times, cancellations,
and makeup sessions. An empty calendar must not erase a baseline class date.

Teaching guide catalogs are public baseline content. A generated coaching brief remains a draft
until an accountable person approves the separate publication request.

Assignment and qualitative-rubric catalogs are also public baseline content. Catalog-backed
Classroom output remains one reviewable `DRAFT` plan; it must not gain student data, grading,
student-visible publication, native rubric writes, or batch execution implicitly.

Applied Classroom action ledgers are private runtime state. Keep them outside tracked content;
never add ledger instances to Git. A write workflow must load the ledger before external access and
persist the returned record after one successful write. An `already_applied` decision is a local
no-op and must not initialize a Google transport.
