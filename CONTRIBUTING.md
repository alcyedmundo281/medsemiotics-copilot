# Contributing to MedSemiotics Teaching Copilot

Thank you for contributing to MedSemiotics Teaching Copilot. To maintain high academic standards, system stability, and data privacy, all contributors must adhere to the following guidelines.

---

## Core Rules & Standards

1. **One Feature per Branch**:
   Always create a descriptive branch for your work (e.g., `feat/syllabus-schema`, `fix/health-check`). Never commit directly to the `main` branch.

2. **Focused Pull Requests**:
   Keep pull requests small, coherent, and focused on a single responsibility. Large multi-feature PRs will be rejected.

3. **Tests Required**:
   Every code change (bug fix or new feature) must include comprehensive unit and/or integration tests. All tests must pass before merging.

4. **No Secrets**:
   Never commit API keys, service account credentials, `.env` files, or authentication tokens. Always use `.env.example` as a template.

5. **No Student-Identifiable Information**:
   Student-identifiable data (names, IDs, emails, grades, student work, medical case patient identifiers) must **never** be committed to version control. Use anonymized or synthetic test fixtures only.

6. **Do Not Modify Unrelated Modules**:
   Keep diffs clean. Do not reformat or modify files outside the immediate scope of your feature or bugfix.

7. **External Write Actions Require Explicit Authorization by Design**:
   In accordance with the **KNOW → REASON → ACT** architecture, reasoning components must not execute write side-effects directly. All external mutations (Google Classroom, Google Drive, grading, publishing) must pass through authorized, auditable action gates.

---

## Development Workflow

### 1. Code Formatting & Linting
Ensure your code satisfies all linting rules:
```bash
ruff check
ruff format --check
```

### 2. Static Type Checking
All code must pass strict type checking without errors or untyped signatures:
```bash
mypy
```

### 3. Test Execution
Run the full test suite and verify test coverage:
```bash
pytest
```

### 4. Continuous Integration
The `CI` workflow (`.github/workflows/ci.yml`) runs the same four gates — `ruff check`,
`ruff format --check`, `mypy`, and `pytest` — on every pull request and on `main`, using the
pinned Python version and the committed `uv.lock`. Run them locally before pushing.

---

## Commit Message Convention

Follow standard conventional commit messages:
- `feat: <description>` for new features
- `fix: <description>` for bug fixes
- `docs: <description>` for documentation changes
- `chore: <description>` for repository maintenance and tool updates
- `test: <description>` for adding or updating tests
