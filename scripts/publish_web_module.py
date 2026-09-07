#!/usr/bin/env python3
"""Publish an educational module to the PowerSemiotics web portal.

Steps established:
1. Copies the prepared HTML module to the target course directory in medsemiotics.
2. Injects the canonical link tag into the module's <head>.
3. Injects a card with hover effect and metadata into the course hub (e.g. gastroenterologia.html).
4. Updates the sitemap.xml.
5. Optionally commits and pushes to origin/main in the medsemiotics repository.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from medsemiotics.domain.web_publication import WebModuleSpec  # noqa: E402
from medsemiotics.services.web_publisher import WebPublisher, WebPublisherError  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("publish_web_module")


def build_parser() -> argparse.ArgumentParser:
    """Create the command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Publish a web module into the PowerSemiotics portal with hub card and sitemap."
    )
    parser.add_argument(
        "--course",
        required=True,
        help="Course identifier (e.g. GASTRO, NEURO, gastroenterologia, neurologia)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the source HTML file",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="Module filename slug without extension (e.g. enfermedad-crohn)",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Display title for the module and its card",
    )
    parser.add_argument(
        "--description",
        required=True,
        help="Summary description shown on the hub card",
    )
    parser.add_argument(
        "--icon",
        default="notes-medical",
        help="FontAwesome icon name (e.g. notes-medical, dna, disease, fire)",
    )
    parser.add_argument(
        "--web-repo",
        type=Path,
        default=None,
        help="Path to the medsemiotics repository root (auto-detected if omitted)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the plan and card HTML without modifying any files",
    )
    parser.add_argument(
        "--auto-git",
        action="store_true",
        help="Automatically commit and push the published files in the medsemiotics repo",
    )
    parser.add_argument(
        "--commit-msg",
        default=None,
        help="Custom Git commit message (default auto-generated)",
    )
    return parser


def main() -> int:
    """Execute the publication script."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        publisher = WebPublisher(web_repo_dir=args.web_repo)
    except WebPublisherError as err:
        logger.error("%s", err)
        return 1

    spec = WebModuleSpec(
        course=args.course,
        slug=args.slug,
        title=args.title,
        description=args.description,
        source_html_path=args.source.resolve(),
        icon=args.icon,
    )

    try:
        plan = publisher.plan_publish(spec)
    except WebPublisherError as err:
        logger.error("Planning failed: %s", err)
        return 1

    print("=" * 70)
    print("PLAN DE PUBLICACIÓN WEB — POWERSEMIOTICS")
    print("=" * 70)
    print(f"Curso:             {plan.section.display_name} ({plan.section.course_code})")
    print(f"Archivo origen:    {plan.spec.source_html_path}")
    print(f"Archivo destino:   {plan.target_module_path}")
    print(f"Hub de sección:    {plan.target_hub_path}")
    print(f"URL Canónica:      {plan.canonical_url}")
    card_status = "Ya existe en el hub" if plan.card_already_exists else "Pendiente de insertar"
    print(f"Tarjeta en hub:    {card_status}")
    print("-" * 70)
    print("HTML DE LA TARJETA:")
    print(plan.card_html)
    print("=" * 70)

    if args.dry_run:
        print("MODO DRY-RUN: No se realizaron cambios en disco ni en git.")
        return 0

    result = publisher.publish_module(
        plan=plan,
        auto_git=args.auto_git,
        commit_message=args.commit_msg,
    )

    print("\n" + result.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
