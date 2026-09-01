#!/usr/bin/env python3
"""Render a reviewable Google Classroom material draft locally.

Nothing is published: the script prints the post for the instructor to review and paste, or the
request body a caller may send under the project's Classroom access policy.
"""

import argparse
import json
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from medsemiotics.integrations.classroom.api_publisher import (  # noqa: E402
    ClassroomApiPublisher,
)
from medsemiotics.integrations.classroom.browser_publisher import (  # noqa: E402
    ClassroomBrowserPublisher,
)


def main() -> int:
    """Render one Classroom material draft and print it."""
    parser = argparse.ArgumentParser(description="MedSemiotics Classroom draft renderer")
    parser.add_argument("--mode", choices=["browser", "api"], default="browser")
    parser.add_argument("--course", default="Neurología", help="Course name or Classroom course id")
    parser.add_argument("--title", required=True, help="Material title")
    parser.add_argument("--description", default="", help="Material body")
    parser.add_argument("--links", nargs="*", help="URLs to attach")
    parser.add_argument("--topic", default="Segundo Hemisemestre", help="Classroom topic")
    args = parser.parse_args()

    if args.mode == "browser":
        plan = ClassroomBrowserPublisher().plan_material(
            course_name=args.course,
            title=args.title,
            description=args.description,
            topic_name=args.topic,
            links=args.links,
        )
        print(plan.render())
    else:
        request = ClassroomApiPublisher().build_material_request(
            course_id=args.course,
            title=args.title,
            description=args.description,
            links=args.links,
        )
        print(json.dumps(request, ensure_ascii=False, indent=2))

    print("\nBORRADOR. Nada fue publicado: revise y publique usted en Google Classroom.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
