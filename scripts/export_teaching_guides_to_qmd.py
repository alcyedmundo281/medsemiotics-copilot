"""CLI script to export teaching guides from catalogs into Quarto (.qmd) and compile to EPUB."""

import argparse
from pathlib import Path

from medsemiotics.services.quarto_guide_exporter import QuartoGuideExporter
from medsemiotics.services.teaching_guide_repository import TeachingGuideRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export teaching guide catalogs to Quarto (.qmd) and compile to EPUB."
    )
    parser.add_argument(
        "--course",
        choices=["GASTRO", "NEURO"],
        default="GASTRO",
        help="Course code (default: GASTRO)",
    )
    parser.add_argument(
        "--semester",
        default="2026-2",
        help="Semester ID (default: 2026-2)",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="Specific topic_id to export (e.g., colitis-ulcerosa). If omitted, exports all.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("qmd_guides"),
        help="Destination directory for .qmd and .epub files (default: qmd_guides/)",
    )
    parser.add_argument(
        "--render-epub",
        action="store_true",
        help="Automatically invoke 'quarto render <file.qmd> --to epub'",
    )

    args = parser.parse_args()

    repo = TeachingGuideRepository(Path("config/teaching_guides"))
    catalog = repo.get_catalog(args.semester, args.course)
    exporter = QuartoGuideExporter(args.output_dir)

    target_guides = catalog.guides
    if args.topic:
        target_guides = [g for g in catalog.guides if g.topic_id == args.topic]
        if not target_guides:
            print(f"Error: Topic '{args.topic}' not found in {args.course} ({args.semester}).")
            return

    print(
        f"Exporting {len(target_guides)} guide(s) for {args.course} ({args.semester}) "
        f"to {args.output_dir.resolve()}..."
    )

    exported_paths: list[Path] = []
    for g in target_guides:
        qmd_path = exporter.export_topic_guide(g, args.course, args.semester)
        exported_paths.append(qmd_path)
        print(f"  [OK] Generated QMD: {qmd_path.name}")

        if args.render_epub:
            try:
                epub_path = exporter.render_to_epub(qmd_path)
                print(f"       -> [EPUB] Rendered: {epub_path.name}")
            except (FileNotFoundError, RuntimeError) as err:
                print(f"       -> [WARN] Could not render EPUB: {err}")

    print(f"Completed: {len(exported_paths)} guide(s) exported.")


if __name__ == "__main__":
    main()
