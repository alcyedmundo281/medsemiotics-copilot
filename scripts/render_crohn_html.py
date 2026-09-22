"""Render standalone HTML web module for Enfermedad de Crohn and Differential Diagnosis.

MedSemiotics Copilot - Cátedra de Gastroenterología y Semiótica Digestiva (HCAM - UCE).
"""

from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "coach_gastro_enfermedad_crohn.html"


def get_crohn_html_content() -> str:
    """Generate the rich interactive HTML web page for Enfermedad de Crohn."""
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def render_crohn_webpage(output_path: Path) -> None:
    """Write the Crohn HTML file to the specified destination."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = get_crohn_html_content()
    output_path.write_text(content, encoding="utf-8")
    print(f"[OK] Rendered Crohn HTML successfully to: {output_path.resolve()}")


if __name__ == "__main__":
    render_crohn_webpage(Path("coach_gastro_enfermedad_crohn.html"))
    render_crohn_webpage(Path("notebooks/coach_gastro_enfermedad_crohn.html"))
