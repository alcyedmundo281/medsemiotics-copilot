#!/usr/bin/env python3
"""Write the teaching-events bridge that secretario-clinico imports into the clinical agenda.

MedSemiotics does not write to Google Calendar. Run this after every syllabus change (for
example after ``sync_syllabus_v2_to_config.py``) and then run, in secretario-clinico:

    uv run python scripts/import_medsemiotics_events.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from medsemiotics.services.teaching_events_bridge import (  # noqa: E402
    build_bridge_document,
    render_bridge_document,
)

SYLLABUS_SOURCES = (
    "silabo_neurologia_v2.yaml",
    "silabo_gastroenterologia_v2.yaml",
)
BRIDGE_DIR = REPO_ROOT / "docs" / "puente_secretario"


def main(argv: list[str] | None = None) -> int:
    """Write ``docs/puente_secretario/eventos_docentes_<semester>.json``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semester", default="2026-2")
    args = parser.parse_args(argv)

    semester_id = str(args.semester)
    syllabus_dir = REPO_ROOT / "config" / "syllabi" / semester_id
    paths = [syllabus_dir / name for name in SYLLABUS_SOURCES]
    syllabi = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in paths]
    document = build_bridge_document(
        semester_id, syllabi, [path.relative_to(REPO_ROOT).as_posix() for path in paths]
    )

    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    output = BRIDGE_DIR / f"eventos_docentes_{semester_id}.json"
    output.write_text(render_bridge_document(document), encoding="utf-8", newline="\n")
    count = len(document["events"])
    print(f"[OK] Puente escrito en {output.relative_to(REPO_ROOT)} ({count} clases)")
    print("     Importe en secretario-clinico: uv run python scripts/import_medsemiotics_events.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
