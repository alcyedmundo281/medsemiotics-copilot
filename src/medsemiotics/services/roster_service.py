"""Read a course roster from a local file that is never tracked in this repository.

Student names, identifiers, and emails are confidential. They stay on the instructor's machine:
this service reads them from a directory given at call time and fails closed when it is absent,
so no roster ever reaches the repository, its logs, or a pull request.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RosterUnavailableError(RuntimeError):
    """Raised when no local roster file backs the requested course."""


@dataclass(frozen=True)
class RubricCriterion:
    """One weighted criterion of a formative rubric."""

    name: str
    weight_percent: int


class StudentRosterService:
    """Load local rosters and render the formative rubric shared with students."""

    def __init__(self, data_root: Path | None = None) -> None:
        """Bind the service to a local roster directory outside the repository."""
        self.data_root = data_root

    def load_roster(self, course_code: str) -> list[dict[str, Any]]:
        """Load the roster for one course from ``<data_root>/<COURSE>.json``.

        Args:
            course_code: Course code, e.g. 'NEURO'.

        Returns:
            The roster entries exactly as stored locally.

        Raises:
            RosterUnavailableError: If no roster directory or file is configured.
        """
        if self.data_root is None:
            msg = (
                "No local roster directory is configured. Rosters hold student data and are "
                "never tracked in this repository."
            )
            raise RosterUnavailableError(msg)

        path = self.data_root / f"{course_code.upper()}.json"
        if not path.is_file():
            msg = f"No local roster file for course '{course_code.upper()}'."
            raise RosterUnavailableError(msg)

        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            msg = f"The local roster for '{course_code.upper()}' is not a list of entries."
            raise RosterUnavailableError(msg)
        return entries

    def generate_rubric(self, assignment_type: str) -> dict[str, Any]:
        """Build the shared formative rubric for one assignment type."""
        criteria = (
            RubricCriterion("Anamnesis y semiótica", 30),
            RubricCriterion("Examen físico y hallazgos", 30),
            RubricCriterion("Razonamiento sindrómico", 40),
        )
        return {
            "title": f"Rúbrica formativa: {assignment_type}",
            "criterios": [
                {"nombre": criterion.name, "peso": criterion.weight_percent}
                for criterion in criteria
            ],
        }
