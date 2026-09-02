"""Tests for the interactive Gastroenterology teaching coach notebook."""

import json
from pathlib import Path


def test_notebook_exists_and_valid() -> None:
    notebook_path = Path("notebooks/coach_gastro_colitis_ulcerosa.ipynb")
    assert notebook_path.exists(), "Notebook file does not exist"

    with notebook_path.open(encoding="utf-8") as f:
        nb = json.load(f)

    assert "cells" in nb
    assert len(nb["cells"]) >= 10
    assert nb["nbformat"] == 4

    cell_types = [c["cell_type"] for c in nb["cells"]]
    assert "markdown" in cell_types
    assert "code" in cell_types

    all_content = " ".join("".join(c["source"]) for c in nb["cells"])

    # Check key syllabus & clinical content presence
    assert "Gastroenterología y Semiótica Digestiva" in all_content
    assert "Colitis Ulcerosa" in all_content
    assert "Montreal" in all_content
    assert "Truelove" in all_content
    assert "SocraticCaseCoach" in all_content
    assert "Ticket de Salida" in all_content


def test_export_notebook_to_yaml_and_md(tmp_path: Path) -> None:
    from scripts.export_notebook_to_yaml import export_notebook_to_yaml

    nb_file = Path("notebooks/coach_gastro_colitis_ulcerosa.ipynb")
    yaml_out = tmp_path / "test_export.yaml"
    md_out = tmp_path / "test_export.md"

    export_notebook_to_yaml(nb_file, yaml_out, md_out)

    assert yaml_out.exists()
    assert md_out.exists()

    content_yaml = yaml_out.read_text(encoding="utf-8")
    assert "Colitis Ulcerosa" in content_yaml
    assert "truelove_witts_criteria_cuag" in content_yaml
    assert "socratic_qa" in content_yaml

    content_md = md_out.read_text(encoding="utf-8")
    assert "Teaching Coach: Gastroenterología" in content_md
    assert "Criterios de Colitis Ulcerosa Aguda Grave" in content_md
