"""Unit tests for WebPublisher and web publication domain models."""

from pathlib import Path

import pytest

from medsemiotics.domain.web_publication import (
    CourseWebSection,
    WebModuleSpec,
)
from medsemiotics.services.web_publisher import WebPublisher, WebPublisherError


def test_course_web_section_resolution() -> None:
    """Test resolution of known course codes to section metadata."""
    gastro = CourseWebSection.from_course("GASTRO")
    assert gastro.section_slug == "gastroenterologia"
    assert gastro.hub_filename == "gastroenterologia.html"
    assert gastro.display_name == "Gastroenterología"

    neuro = CourseWebSection.from_course("NEURO")
    assert neuro.section_slug == "neurologia"
    assert neuro.hub_filename == "neurologia.html"
    assert neuro.display_name == "Neurología"

    custom = CourseWebSection.from_course("farmacologia")
    assert custom.section_slug == "farmacologia"
    assert custom.hub_filename == "farmacologia.html"


def test_web_module_spec_validation(tmp_path: Path) -> None:
    """Test validation and normalization in WebModuleSpec."""
    source_file = tmp_path / "module.html"
    source_file.write_text("<h1>Test</h1>", encoding="utf-8")

    spec = WebModuleSpec(
        course="GASTRO",
        slug="Enfermedad-Crohn.html",
        title="Enfermedad de Crohn",
        description="Descripción de prueba",
        source_html_path=source_file,
        icon="fas fa-notes-medical",
    )
    assert spec.slug == "enfermedad-crohn"
    assert spec.icon == "notes-medical"
    assert spec.get_canonical_url("gastroenterologia") == (
        "https://powersemiotics.com/medsemiotics/gastroenterologia/enfermedad-crohn.html"
    )
    assert spec.get_relative_href("gastroenterologia") == (
        "gastroenterologia/enfermedad-crohn.html"
    )

    with pytest.raises(ValueError, match="Module slug must not be empty"):
        WebModuleSpec(
            course="GASTRO",
            slug=".html",
            title="Title",
            description="Desc",
            source_html_path=source_file,
        )


def test_format_card_html() -> None:
    """Test card HTML formatting with standard Tailwind layout."""
    card = WebPublisher.format_card_html(
        title="Enfermedad de Crohn",
        description="Semiótica y diagnóstico diferencial",
        relative_href="gastroenterologia/enfermedad-crohn.html",
        icon="notes-medical",
    )
    assert "<!-- Módulo: Enfermedad de Crohn -->" in card
    assert 'href="gastroenterologia/enfermedad-crohn.html"' in card
    assert "fa-notes-medical" in card
    assert "Módulo: Enfermedad de Crohn" in card
    assert "Semiótica y diagnóstico diferencial" in card


def test_ensure_canonical_link() -> None:
    """Test canonical link addition and update in HTML head."""
    html_without_canonical = """<!DOCTYPE html>
<html>
<head>
  <title>Sample</title>
</head>
<body>
  <h1>Sample</h1>
</body>
</html>"""
    canonical_url = "https://powersemiotics.com/medsemiotics/gastroenterologia/test.html"
    updated = WebPublisher.ensure_canonical_link(html_without_canonical, canonical_url)
    assert f'<link rel="canonical" href="{canonical_url}" />' in updated

    # Replace existing canonical
    html_with_old_canonical = """<!DOCTYPE html>
<html>
<head>
  <link rel="canonical" href="https://old-url.com/page.html" />
  <title>Sample</title>
</head>
<body></body></html>"""
    replaced = WebPublisher.ensure_canonical_link(html_with_old_canonical, canonical_url)
    assert f'<link rel="canonical" href="{canonical_url}" />' in replaced
    assert "old-url.com" not in replaced


def test_inject_card_into_hub() -> None:
    """Test card injection into hub grid."""
    sample_hub = """<!DOCTYPE html>
<html>
<body>
  <main>
    <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      <!-- Existing Card -->
      <a href="gastroenterologia/existing.html">Existing</a>
    </div>
  </main>
</body>
</html>"""

    card = "<!-- New Card -->\n<a href=\"gastroenterologia/new.html\">New</a>"
    injected = WebPublisher.inject_card_into_hub(sample_hub, card, "gastroenterologia/new.html")
    assert "<!-- New Card -->" in injected
    assert "<!-- Existing Card -->" in injected

    # Idempotent: injecting existing card does not duplicate
    re_injected = WebPublisher.inject_card_into_hub(injected, card, "gastroenterologia/new.html")
    assert re_injected == injected


def test_publish_workflow_in_mock_repo(tmp_path: Path) -> None:
    """Test full publish plan and execution in a mock repository."""
    repo_dir = tmp_path / "medsemiotics"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    (repo_dir / "index.html").write_text("<h1>Index</h1>", encoding="utf-8")

    gastro_dir = repo_dir / "gastroenterologia"
    gastro_dir.mkdir()
    (gastro_dir / "index.html").write_text("Redirect", encoding="utf-8")

    hub_file = repo_dir / "gastroenterologia.html"
    hub_file.write_text(
        """<!DOCTYPE html>
<html>
<body>
  <main>
    <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      <!-- Existing -->
    </div>
  </main>
</body>
</html>""",
        encoding="utf-8",
    )

    sitemap_file = repo_dir / "sitemap.xml"
    sitemap_file.write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
        encoding="utf-8",
    )

    source_html = tmp_path / "source_module.html"
    source_html.write_text(
        "<!DOCTYPE html><html><head></head><body>Crohn Content</body></html>",
        encoding="utf-8",
    )

    publisher = WebPublisher(web_repo_dir=repo_dir)

    spec = WebModuleSpec(
        course="GASTRO",
        slug="enfermedad-crohn",
        title="Enfermedad de Crohn",
        description="Módulo interactivo completo",
        source_html_path=source_html,
        icon="notes-medical",
    )

    plan = publisher.plan_publish(spec)
    assert not plan.card_already_exists
    assert plan.target_module_path == gastro_dir / "enfermedad-crohn.html"

    result = publisher.publish_module(plan=plan, auto_git=False)
    assert result.module_copied
    assert result.hub_updated
    assert (gastro_dir / "enfermedad-crohn.html").is_file()

    published_content = (gastro_dir / "enfermedad-crohn.html").read_text(encoding="utf-8")
    assert "Crohn Content" in published_content
    assert 'link rel="canonical"' in published_content

    updated_hub = hub_file.read_text(encoding="utf-8")
    assert "gastroenterologia/enfermedad-crohn.html" in updated_hub
    assert "Enfermedad de Crohn" in updated_hub


def test_publisher_errors(tmp_path: Path) -> None:
    """Test proper exception raising on invalid inputs."""
    with pytest.raises(WebPublisherError, match="not a valid medsemiotics repository"):
        WebPublisher(web_repo_dir=tmp_path / "non_existent")

    valid_repo = tmp_path / "valid_repo"
    valid_repo.mkdir()
    (valid_repo / ".git").mkdir()
    (valid_repo / "index.html").write_text("index", encoding="utf-8")

    publisher = WebPublisher(web_repo_dir=valid_repo)

    missing_source = WebModuleSpec(
        course="GASTRO",
        slug="test",
        title="Test",
        description="Desc",
        source_html_path=tmp_path / "not_found.html",
    )
    with pytest.raises(WebPublisherError, match="Source HTML file does not exist"):
        publisher.plan_publish(missing_source)
