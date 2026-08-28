# MedSemiotics Teaching Copilot

**MedSemiotics Teaching Copilot** is an AI-assisted academic teaching and content-management platform for Neurology and Gastroenterology.

> [!CAUTION]
> **Privacy and Data Protection**: Student-identifiable data (names, IDs, emails, grades, submissions, or identifiable work) must **NEVER** be committed to Git. All production datasets, student records, and credential tokens are strictly ignored via `.gitignore`.

---

## Architectural Principles

The platform is structured around the strict conceptual separation of three operational layers:

- **KNOW** (Domain Data & State): Academic state, course syllabi, teaching logs, assignments, medical evidence references, and media metadata.
- **REASON** (Agents, Analytics & Inference): Agentic analysis, psychometrics, pedagogical analytics, and recommendation logic.
- **ACT** (External Actions & Side Effects): Publishing, Google Classroom writes, Google Drive writes, and grading operations. **ACT actions require explicit authorization and are never coupled directly to reasoning logic.**

For details, refer to [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Technical Baseline

- **Language**: Python 3.12+
- **API Framework**: FastAPI
- **Data Validation**: Pydantic v2
- **Configuration**: YAML / Pydantic Settings
- **Package Management**: `uv`
- **Linting & Formatting**: `ruff`
- **Type Checking**: `mypy` (strict mode)
- **Testing**: `pytest` + `pytest-cov`

---

## Project Structure

```
medsemiotics-teaching-copilot/
│
├── src/
│   └── medsemiotics/
│       ├── __init__.py
│       ├── domain/            # KNOW: Data models and domain entities
│       ├── services/          # Business logic and domain services
│       ├── agents/            # REASON: Pedagogical and reasoning agents
│       ├── integrations/      # External service connectors
│       └── api/               # FastAPI endpoints (GET /health)
│
├── tests/                     # Test suite
├── config/
│   └── semesters/             # Semester configuration YAML files
├── docs/                      # Technical documentation
├── scripts/                   # Utility and maintenance scripts
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── ARCHITECTURE.md
└── CONTRIBUTING.md
```

---

## Semester Configuration

- **Semester Files**: Individual semester definitions are located under `config/semesters/` (e.g. `config/semesters/2026-2.yaml`).
- **Active Semester Pointer**: `config/current_semester.yaml` points to the active semester ID without duplicating configuration.
- **Local State**: Semester configuration is stored as pure, validated local YAML files within the repository.
- **Integration Decoupling**: External integrations (such as Google Drive folders or Classroom sync) are intentionally separated and not part of this domain configuration layer.

---

## Academic State: Planned Curriculum vs. Actual Teaching History

The platform enforces a strict domain distinction between two independent sources of truth:

- **`SyllabusPlan` (Intended Teaching Sequence)**: Models what the official course syllabus intends to teach, in what sequential order (`planned_order`), and target week (`planned_week`).
- **`TeachingSession` (Actual Teaching History)**: Models historical reality—what was actually delivered in a specific classroom/clinical session, the date, session sequence, and topic coverage status (`CoverageStatus`: introduced, partial, completed, reviewed, skipped).

> [!IMPORTANT]
> `SyllabusPlan` and `TeachingSession` **must never be treated as equivalent**. A topic may be planned and never taught, taught across multiple sessions, partially delivered, reviewed, or taught out of the planned order.

---

## Quickstart & Development

### 1. Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed, along with Python 3.12 or higher.

### 2. Environment Setup

Create and activate a virtual environment, then install dependencies:

```bash
# Create virtual environment with uv
uv venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install project and dev dependencies
uv pip install -e ".[dev]"
```

### 3. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

### 4. Running Quality Checks

```bash
# Run linter & formatter checks
ruff check
ruff format --check

# Run static type analysis
mypy

# Run tests with coverage
pytest
```

---

## Contribution Guidelines

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on code quality, branch workflows, and security practices.
