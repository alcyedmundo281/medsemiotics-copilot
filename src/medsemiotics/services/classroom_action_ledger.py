"""Private, atomic persistence for applied Google Classroom actions."""

import json
import os
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from medsemiotics.domain.classroom_action import ClassroomActionRecord
from medsemiotics.domain.exceptions import (
    ClassroomActionLedgerPersistenceError,
    ClassroomActionLedgerValidationError,
)

LEDGER_SCHEMA_VERSION: Final[int] = 1
_LEDGER_KEYS: Final[frozenset[str]] = frozenset({"schema_version", "records"})


class ClassroomActionLedgerRepository:
    """Store the minimal private evidence needed to prevent duplicate Classroom drafts.

    The ledger path is supplied by the operator and must remain outside tracked public content.
    Writes use a temporary file in the same directory followed by an atomic replacement.
    """

    def __init__(self, path: Path) -> None:
        """Initialize the repository at one explicit private JSON path."""
        self._path = path.expanduser().resolve()

    @property
    def path(self) -> Path:
        """Return the resolved private ledger path."""
        return self._path

    def load(self) -> tuple[ClassroomActionRecord, ...]:
        """Load and validate every applied-action record.

        A missing file represents an empty ledger. A present file fails closed when its envelope,
        schema version, record types, or action identities are inconsistent.
        """
        if not self._path.exists():
            return ()
        if not self._path.is_file():
            msg = "Classroom action ledger path is not a regular file."
            raise ClassroomActionLedgerValidationError(msg)

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as err:
            msg = "Classroom action ledger could not be read as valid UTF-8 JSON."
            raise ClassroomActionLedgerValidationError(msg) from err

        if not isinstance(payload, dict) or set(payload) != _LEDGER_KEYS:
            msg = "Classroom action ledger must contain only schema_version and records."
            raise ClassroomActionLedgerValidationError(msg)
        if payload["schema_version"] != LEDGER_SCHEMA_VERSION:
            msg = (
                "Unsupported Classroom action ledger schema version; "
                f"expected {LEDGER_SCHEMA_VERSION}."
            )
            raise ClassroomActionLedgerValidationError(msg)

        raw_records = payload["records"]
        if not isinstance(raw_records, list):
            msg = "Classroom action ledger records must be a JSON array."
            raise ClassroomActionLedgerValidationError(msg)

        try:
            records = tuple(ClassroomActionRecord.model_validate(item) for item in raw_records)
        except (ValidationError, TypeError) as err:
            msg = "Classroom action ledger contains an invalid applied-action record."
            raise ClassroomActionLedgerValidationError(msg) from err

        identities = [record.identity_key for record in records]
        if len(identities) != len(set(identities)):
            msg = "Classroom action ledger contains duplicate action identities."
            raise ClassroomActionLedgerValidationError(msg)
        return records

    def append(self, record: ClassroomActionRecord) -> ClassroomActionRecord:
        """Persist one new record without overwriting a conflicting action identity.

        Re-appending the exact same immutable record is a harmless no-op. Reusing an identity with
        different evidence fails closed because the correct external result would be ambiguous.
        """
        records = self.load()
        existing = next(
            (item for item in records if item.identity_key == record.identity_key),
            None,
        )
        if existing is not None:
            if existing == record:
                return existing
            msg = "Classroom action identity already exists with different ledger evidence."
            raise ClassroomActionLedgerValidationError(msg)

        self._persist((*records, record))
        return record

    def _persist(self, records: Collection[ClassroomActionRecord]) -> None:
        """Atomically replace the ledger with a canonical JSON representation."""
        payload = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "records": [record.model_dump(mode="json") for record in records],
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        temporary_path: Path | None = None

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(rendered)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)

            temporary_path.chmod(0o600)
            temporary_path.replace(self._path)
            self._path.chmod(0o600)
        except OSError as err:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            msg = "Classroom action ledger could not be persisted atomically."
            raise ClassroomActionLedgerPersistenceError(msg) from err
