#!/usr/bin/env python3
"""Script CLI local unificado para publicación en Google Classroom."""

import argparse
import sys
from pathlib import Path

# Configurar PYTHONPATH interno
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from medsemiotics.integrations.classroom.browser_publisher import ClassroomBrowserPublisher
from medsemiotics.integrations.classroom.api_publisher import ClassroomApiPublisher

def main():
    parser = argparse.ArgumentParser(description="MedSemiotics Classroom Publisher CLI")
    parser.add_argument("--mode", choices=["browser", "api"], default="browser", help="Modo de ejecucion (browser o api)")
    parser.add_argument("--course", default="Neurología", help="Nombre del curso")
    parser.add_argument("--title", required=True, help="Titulo del material")
    parser.add_argument("--description", default="", help="Descripcion / Contenido")
    parser.add_argument("--links", nargs="*", help="URLs a adjuntar")
    parser.add_argument("--topic", default="Segundo Hemisemestre", help="Tema en Trabajo de Clase")

    args = parser.parse_args()

    print("=" * 70)
    print("[+] MedSemiotics Classroom Publisher -- Unificado")
    print("=" * 70)

    if args.mode == "browser":
        publisher = ClassroomBrowserPublisher()
        publisher.publish_material(
            course_name=args.course,
            title=args.title,
            description=args.description,
            topic_name=args.topic,
            links=args.links,
        )
    else:
        publisher = ClassroomApiPublisher()
        publisher.create_material(
            course_id=args.course,
            title=args.title,
            description=args.description,
            links=args.links,
        )

    print("=" * 70)
    print("[OK] Publicacion procesada con exito.")
    print("=" * 70)

if __name__ == "__main__":
    main()