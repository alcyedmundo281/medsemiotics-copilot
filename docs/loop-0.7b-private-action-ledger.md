# Loop 0.7B — private persistent Classroom action ledger

## Outcome

Loop 0.7B makes the existing one-action Classroom idempotency survive a process restart. The
operator workflow no longer depends on manually copying a ledger entry between invocations.

`ClassroomActionLedgerRepository` stores only the minimal evidence returned by the existing writer:

- deterministic action identity;
- external course and coursework references;
- timezone-aware application timestamp;
- accountable actor.

It stores no student identity, roster, submission, grade, credential, token, instructions, or
assignment body. The JSON file is private runtime state, not a repository artifact.

## Rerunnable workflow

```text
reviewed single-action plan
          +
named content-bound approval
          +
private ledger loaded before external access
          |
          v
ClassroomActionAuthorizer
    | authorized                         | already_applied
    v                                    v
one DRAFT-only writer call        local success/no-op
    |                              no deployment or Google call
    v
atomic ledger append
```

The operator supplies the same private path on every invocation. The recommended filename suffix
is `.classroom-ledger.json`, which Git ignores defensively even though the file should live in a
private persistent runtime location:

```bash
python scripts/classroom_write_smoke.py \
    --course-id <linked course id> \
    --topic-id <tracked syllabus topic> \
    --title "<reviewed title>" \
    --approved-by "<named approver>" \
    --ledger-file <private persistent JSON path>
```

On the first successful run, the writer creates exactly one coursework item in `DRAFT` state and
the repository atomically persists its record. An identical later run loads that record, receives
`already_applied`, and returns before loading the Apps Script deployment or constructing a Google
transport.

## Fail-closed behavior

- Missing ledger means empty state; malformed JSON, unexpected fields, unsupported schema versions,
  invalid records, and duplicate identities are rejected.
- Re-appending the exact immutable record is harmless; the same identity with different evidence
  is rejected as a conflict.
- Persistence writes a same-directory temporary file, flushes it, and atomically replaces the
  ledger. A failed replacement removes the temporary file and reports a dedicated error.
- If Google succeeds but local persistence fails, the script prints the minimal recovery identity
  and external reference and exits distinctly. The operator must repair the private ledger before
  retrying.

## Boundaries

This increment does not add mobile approval, trusted automation, bulk operations, native Classroom
rubric creation, publishing to students, grades, roster access, submissions, or new OAuth scopes.
The public repository includes the repository code, tests, and procedure only—never a ledger
instance.

## Exit criteria

- a versioned and strictly validated private ledger;
- atomic persistence and explicit conflict handling;
- the operator script requires a ledger path and loads it before external setup;
- a persisted record makes the same plan a no-op after a new process starts;
- no student, credential, grade, or assignment-body data is stored;
- pytest, Ruff, formatting, strict mypy, and public CI pass.
