"""Unit tests for Quarto guide exporter service."""

from pathlib import Path
import pytest

from medsemiotics.domain.teaching_coach import TeachingTopicGuide
from medsemiotics.services.quarto_guide_exporter import (
    QuartoGuideExporter,
    format_guide_as_qmd,
)
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository


def test_format_guide_as_qmd() -> None:
    guide = TeachingTopicGuide(
        topic_id="colitis-ulcerosa",
        topic_title="Colitis ulcerosa: semiología, extensión y actividad",
        learning_objectives=["Reconocer el patrón clínico"],
        critical_points=["Diarrea con sangre y moco"],
        teaching_questions=["¿Qué elementos separan diarrea inflamatoria de infecciosa?"],
        common_pitfalls=["Asumir causa infecciosa"],
        material_notes=["Cuadro comparativo"],
    )

    qmd = format_guide_as_qmd(guide, "GASTRO", "2026-2")

    assert 'title: "Colitis ulcerosa: semiología, extensión y actividad"' in qmd
    assert "format:" in qmd
    assert "epub:" in qmd
    assert "html:" in qmd
    assert "## 1. 🎯 Resultados de Aprendizaje" in qmd
    assert "Reconocer el patrón clínico" in qmd
    assert "Diarrea con sangre y moco" in qmd


def test_quarto_guide_exporter_export_all(tmp_path: Path) -> None:
    repo = TeachingGuideRepository(Path("config/teaching_guides"))
    catalog = repo.get_catalog("2026-2", "GASTRO")

    exporter = QuartoGuideExporter(tmp_path)
    generated = exporter.export_all_from_catalog(catalog, "2026-2")

    assert len(generated) == len(catalog.guides)
    for p in generated:
        assert p.is_file()
        assert p.suffix == ".qmd"
        content = p.read_text(encoding="utf-8")
        assert "format:" in content
        assert "epub:" in content


def test_render_to_epub_raises_when_file_missing(tmp_path: Path) -> None:
    missing_file = tmp_path / "nonexistent.qmd"
    with pytest.raises(FileNotFoundError):
        QuartoGuideExporter.render_to_epub(missing_file)
