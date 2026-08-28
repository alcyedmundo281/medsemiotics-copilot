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

## Academic State Projection

Academic state is derived through pure, deterministic domain projection rather than AI inference or probabilistic scoring:

$$\text{SyllabusPlan} + \text{TeachingSession history} \longrightarrow \text{CourseAcademicState}$$

The projection engine explicitly distinguishes:
- **Planned Topics**: Defined sequentially in `SyllabusPlan` with mandatory/elective flags.
- **Taught Progress (`TopicProgress`)**: Tracks `session_count`, `first_taught_date`, `last_taught_date`, and status (`not_started`, `in_progress`, `completed`, `skipped`).
- **Completed as Terminal**: Once a topic reaches `completed` in historical sessions, later events cannot regress its completion status.
- **Skipped Topics**: Retained explicitly as `skipped` rather than ignored, so pedagogical reviews can evaluate remediation.
- **Unplanned Taught Content**: Real-world lectures often introduce impromptu clinical topics not in the syllabus; the projector isolates these via `find_unplanned_taught_topic_ids()` without polluting the formal syllabus model.

---

## Teaching Schedule and Position

The platform combines course meeting rules with syllabus and actual teaching history to resolve pacing for any explicit reference date:

$$\text{Schedule} + \text{Syllabus} + \text{Teaching History} + \text{Target Date} \longrightarrow \text{TeachingPosition}$$

- **`CourseTeachingSchedule`**: Defines term boundaries (`teaching_start_date` .. `teaching_end_date`), recurring weekly meeting rules (`ClassMeetingRule`), and overrides (`ScheduleException`: `cancelled`, `no_class`, `makeup`).
- **`TeachingPosition`**: Evaluates whether the target date is a class date, computes `expected_session_count`, `actual_session_count`, `expected_topic_order`, `current_topic_id`, and pacing assessment (`TeachingPaceStatus`: `ahead`, `on_track`, `behind`, `not_started`, `complete`, `unavailable`).
- **Placeholder Schedules**: Default schedule files in `config/schedules/` are initialized with `enabled: false` as structural placeholders until actual institutional timetables are configured.
- **Deterministic Date Invariant**: All date calculations require an explicit `target_date` argument. No service silently queries the system clock (`date.today()` or `datetime.now()`).

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
