"""Service to export teaching guides into Quarto documents (.qmd) and compile to EPUB/HTML."""

import shutil
import subprocess
from pathlib import Path

from medsemiotics.domain.teaching_coach import CourseTeachingGuideCatalog, TeachingTopicGuide


def format_guide_as_qmd(
    guide: TeachingTopicGuide,
    course_code: str,
    semester_id: str,
    author: str = "Cátedra de Gastroenterología y Semiótica Digestiva — UCE / HCAM",
    date: str = "2026-09-02",
) -> str:
    """Formats a TeachingTopicGuide into a complete Quarto Markdown (.qmd) document."""
    qmd_lines = [
        "---",
        f'title: "{guide.topic_title}"',
        f'subtitle: "Guía Docente y Razonamiento Clínico — {course_code} ({semester_id})"',
        f'author: "{author}"',
        f'date: "{date}"',
        "lang: es",
        "format:",
        "  epub:",
        "    toc: true",
        "    toc-depth: 3",
        '    toc-title: "Índice de la Guía"',
        "    number-sections: false",
        "  html:",
        "    toc: true",
        "    toc-depth: 3",
        "    theme: cosmo",
        "    code-fold: true",
        "    embed-resources: true",
        "---",
        "",
        f"# {guide.topic_title}",
        "",
        f"**Asignatura:** {course_code} · **Semestre:** {semester_id}  ",
        f"**Tópico / Código:** `{guide.topic_id}`  ",
        "**Marco Pedagógico:** `KNOW -> REASON -> ACT` (Material docente para discusión)",
        "",
        "---",
        "",
        "## 1. 🎯 Resultados de Aprendizaje",
        "",
    ]
    for obj in guide.learning_objectives:
        qmd_lines.append(f"- {obj}")

    qmd_lines.extend(
        [
            "",
            "## 2. ⚡ Puntos Críticos y Semiótica Clave",
            "",
        ]
    )
    for pt in guide.critical_points:
        qmd_lines.append(f"- {pt}")

    qmd_lines.extend(
        [
            "",
            "## 3. ❓ Preguntas Socráticas para la Discusión Docente",
            "",
        ]
    )
    for q in guide.teaching_questions:
        qmd_lines.append(f"1. **{q}**")

    qmd_lines.extend(
        [
            "",
            "## 4. ⚠️ Errores Frecuentes y Trampas Diagnósticas",
            "",
        ]
    )
    for p in guide.common_pitfalls:
        qmd_lines.append(f"- **Trampa / Error:** {p}")

    qmd_lines.extend(
        [
            "",
            "## 5. 📚 Materiales y Notas Docentes",
            "",
        ]
    )
    for m in guide.material_notes:
        qmd_lines.append(f"- {m}")

    qmd_lines.extend(
        [
            "",
            "---",
            f"*MedSemiotics Copilot — {course_code} {semester_id} — UCE / HCAM*",
            "",
        ]
    )
    return "\n".join(qmd_lines)


class QuartoGuideExporter:
    """Service to export guide catalogs into .qmd and invoke Quarto for EPUB/HTML rendering."""

    def __init__(self, output_dir: Path) -> None:
        """Initialize exporter with destination directory for .qmd files."""
        self.output_dir = output_dir

    def export_topic_guide(
        self,
        guide: TeachingTopicGuide,
        course_code: str,
        semester_id: str,
        filename: str | None = None,
    ) -> Path:
        """Generates and writes a single .qmd file for a topic guide."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = filename or f"{course_code.lower()}_{guide.topic_id.replace('-', '_')}.qmd"
        target_path = self.output_dir / safe_name

        content = format_guide_as_qmd(guide, course_code, semester_id)
        target_path.write_text(content, encoding="utf-8")
        return target_path

    def export_all_from_catalog(
        self, catalog: CourseTeachingGuideCatalog, semester_id: str
    ) -> list[Path]:
        """Exports every topic in the catalog into a separate .qmd file."""
        generated: list[Path] = []
        for guide in catalog.guides:
            path = self.export_topic_guide(guide, catalog.course_code, semester_id)
            generated.append(path)
        return generated

    @staticmethod
    def render_to_epub(qmd_file: Path, output_dir: Path | None = None) -> Path:
        """Renders a .qmd file to EPUB using quarto CLI if available."""
        if not qmd_file.is_file():
            msg = f"QMD source file not found: {qmd_file}"
            raise FileNotFoundError(msg)

        quarto_bin = shutil.which("quarto")
        if not quarto_bin:
            msg = (
                "Quarto CLI was not found on system PATH. "
                f"Please install Quarto (https://quarto.org) and run: quarto render {qmd_file} --to epub"
            )
            raise RuntimeError(msg)

        cmd = [quarto_bin, "render", str(qmd_file), "--to", "epub"]
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            cmd.extend(["--output-dir", str(output_dir)])

        subprocess.run(cmd, check=True)
        epub_filename = qmd_file.with_suffix(".epub").name
        dest_dir = output_dir or qmd_file.parent
        return dest_dir / epub_filename
