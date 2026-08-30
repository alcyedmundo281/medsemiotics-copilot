"""Domain tests for one folder-backed Classroom material package."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from medsemiotics.domain.classroom_action import ClassroomActionPlan, ClassroomActionType
from medsemiotics.domain.classroom_material import (
    ClassroomMaterialPackagePlan,
    ClassroomMaterialResource,
    MaterialResourceType,
)

NOW = datetime(2026, 8, 30, 5, 0, tzinfo=UTC)


def make_resource(index: int = 1, **updates: object) -> ClassroomMaterialResource:
    values: dict[str, object] = {
        "resource_type": MaterialResourceType.PDF,
        "title": f"Lectura {index}",
        "url": f"https://drive.google.com/file/d/pdf-{index}/view",
    }
    values.update(updates)
    return ClassroomMaterialResource(**values)  # type: ignore[arg-type]


def make_plan(**updates: object) -> ClassroomMaterialPackagePlan:
    values: dict[str, object] = {
        "semester_id": "2026-2",
        "course_code": "neuro",
        "external_course_id": "course-123",
        "topic_id": "neuro-intro-localizacion",
        "title": "Material de localización neurológica",
        "description": "Recursos revisados para la sesión.",
        "folder_url": "https://drive.google.com/drive/folders/folder-123",
        "resources": (make_resource(),),
        "prepared_by": "faculty-owner",
        "prepared_at": NOW,
    }
    values.update(updates)
    return ClassroomMaterialPackagePlan(**values)  # type: ignore[arg-type]


class TestClassroomMaterialPackagePlan:
    def test_normalizes_and_fingerprints_one_package(self) -> None:
        plan = make_plan()

        assert plan.course_code == "NEURO"
        assert plan.action_type is ClassroomActionType.PUBLISH_COURSEWORK_MATERIAL
        assert len(plan.identity_key) == 64
        assert len(plan.content_fingerprint) == 64

    def test_content_change_requires_new_approval_but_keeps_identity(self) -> None:
        original = make_plan()
        changed = make_plan(resources=(make_resource(url="https://example.org/revised.pdf"),))

        assert changed.identity_key == original.identity_key
        assert changed.content_fingerprint != original.content_fingerprint

    def test_allows_folder_plus_nineteen_resources(self) -> None:
        plan = make_plan(resources=tuple(make_resource(index) for index in range(19)))

        assert len(plan.resources) == 19

    def test_refuses_more_than_twenty_total_materials(self) -> None:
        with pytest.raises(ValidationError, match="at most 19 items"):
            make_plan(resources=tuple(make_resource(index) for index in range(20)))

    def test_refuses_duplicate_urls_including_folder(self) -> None:
        with pytest.raises(ValidationError, match="URLs must be unique"):
            make_plan(
                resources=(
                    make_resource(
                        url="https://drive.google.com/drive/folders/folder-123",
                    ),
                )
            )

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.org/file.pdf",
            "https://user:password@example.org/file.pdf",
            "relative/file.pdf",
        ],
    )
    def test_requires_safe_https_resource_urls(self, url: str) -> None:
        with pytest.raises(ValidationError, match="absolute HTTPS URL"):
            make_resource(url=url)

    def test_refuses_hidden_student_targeting(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ClassroomMaterialPackagePlan.model_validate(
                {**make_plan().model_dump(), "student_ids": ["student-1"]}
            )

    def test_legacy_coursework_plan_cannot_use_material_action(self) -> None:
        with pytest.raises(ValidationError, match="only describe create_coursework_draft"):
            ClassroomActionPlan(
                action_type=ClassroomActionType.PUBLISH_COURSEWORK_MATERIAL,
                semester_id="2026-2",
                course_code="NEURO",
                external_course_id="course-123",
                topic_id="neuro-intro-localizacion",
                title="Not a legacy coursework plan",
                prepared_by="operator",
                prepared_at=NOW,
            )
