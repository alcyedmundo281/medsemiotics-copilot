"""Render standalone HTML preview for Gastroenterology Teaching Coach."""

from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "templates" / "coach_gastro_colitis_ulcerosa.html"


def render_html_preview(output_path: Path) -> None:
    html_content = TEMPLATE_PATH.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[OK] Rendered HTML successfully to: {output_path.resolve()}")


if __name__ == "__main__":
    out_file = Path("coach_gastro_colitis_ulcerosa.html")
    render_html_preview(out_file)
    render_html_preview(Path("notebooks/coach_gastro_colitis_ulcerosa.html"))
