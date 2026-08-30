"""Static safety contract for the deployable Apps Script material route."""

import json
from pathlib import Path

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "apps_script" / "classroom_course_discovery.gs"
MANIFEST_PATH = PROJECT_ROOT / "scripts" / "apps_script" / "appsscript.json"


def test_manifest_declares_the_exact_material_scope() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE in manifest["oauthScopes"]


def test_material_route_is_single_published_grade_free_operation() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")
    material_route = script.split("function publishCourseworkMaterial", maxsplit=1)[1].split(
        "function isSafeHttpsUrl", maxsplit=1
    )[0]

    assert "Classroom.Courses.CourseWorkMaterials.create" in material_route
    assert "state: 'PUBLISHED'" in material_route
    assert "resources.length > 19" in material_route
    assert "isSafeHttpsUrl" in material_route
    for prohibited in ("maxPoints", "student_ids", "individualStudentsOptions", "assigneeMode"):
        assert prohibited not in material_route
