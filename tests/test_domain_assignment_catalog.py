"""Domain tests for faculty-reviewed assignment and rubric catalogs."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from medsemiotics.domain.assignment_catalog import (
    AssignmentRubric,
    AssignmentTemplate,
    CatalogAssignmentDraft,
    CourseAssignmentCatalog,
    RubricCriterion,
    RubricLevel,
)
from medsemiotics.domain.classroom_action import ClassroomActionPlan, ClassroomActionType


def make_levels() -> tuple[RubricLevel, ...]:
    return (
        RubricLevel(level_id="integrated", label="Integrated", description="Complete."),
        RubricLevel(level_id="developing", label="Developing", description="Needs revision."),
    )


def make_criteria(**updates: object) -> tuple[RubricCriterion, ...]:
    first: dict[str, object] = {
        "criterion_id": "clinical-structure",
        "title": "Clinical structure",
        "description": "Organizes the examination.",
        "weight_percent": 60,
    }
    first.update(updates)
    return (
        RubricCriterion(**first),  # type: ignore[arg-type]
        RubricCriterion(
            criterion_id="reasoning",
            title="Reasoning",
            description="Explains the interpretation.",
            weight_percent=40,
        ),
    )


def make_rubric(**updates: object) -> AssignmentRubric:
    values: dict[str, object] = {
        "rubric_id": "neuro-reasoning",
        "title": "Neurological reasoning rubric",
        "levels": make_levels(),
        "criteria": make_criteria(),
    }
    values.update(updates)
    return AssignmentRubric(**values)  # type: ignore[arg-type]


def make_assignment(**updates: object) -> AssignmentTemplate:
    values: dict[str, object] = {
        "assignment_id": "cranial-nerves-case",
        "topic_id": "cranial-nerves",
        "title": "Cranial nerve pattern",
        "prompt": "Analyze a synthetic case.",
        "deliverables": ["Finding table.", "Reasoned localization."],
        "rubric_id": "neuro-reasoning",
        "suggested_due_days": 7,
    }
    values.update(updates)
    return AssignmentTemplate(**values)  # type: ignore[arg-type]


def make_catalog(**updates: object) -> CourseAssignmentCatalog:
    values: dict[str, object] = {
        "semester_id": "2026-2",
        "course_code": "NEURO",
        "enabled": True,
        "assignments": [make_assignment()],
        "rubrics": [make_rubric()],
    }
    values.update(updates)
    return CourseAssignmentCatalog(**values)  # type: ignore[arg-type]


def make_plan(**updates: object) -> ClassroomActionPlan:
    values: dict[str, object] = {
        "action_type": ClassroomActionType.CREATE_COURSEWORK_DRAFT,
        "semester_id": "2026-2",
        "course_code": "NEURO",
        "external_course_id": "770001",
        "topic_id": "cranial-nerves",
        "title": "Cranial nerve pattern",
        "instructions": "Review the synthetic case.",
        "due_date": date(2026, 9, 10),
        "prepared_by": "course-director",
        "prepared_at": datetime(2026, 8, 30, tzinfo=UTC),
    }
    values.update(updates)
    return ClassroomActionPlan(**values)  # type: ignore[arg-type]


class TestAssignmentRubric:
    def test_requires_weights_to_total_one_hundred(self) -> None:
        with pytest.raises(ValidationError, match="must total 100"):
            make_rubric(criteria=make_criteria(weight_percent=50))

    def test_rejects_duplicate_level_ids(self) -> None:
        duplicate = make_levels()[0]
        with pytest.raises(ValidationError, match="must not repeat a level_id"):
            make_rubric(levels=[duplicate, duplicate])

    def test_rejects_duplicate_criterion_ids(self) -> None:
        criterion = make_criteria()[0].model_copy(update={"weight_percent": 50})
        with pytest.raises(ValidationError, match="must not repeat a criterion_id"):
            make_rubric(criteria=[criterion, criterion])

    def test_forbids_student_score_fields(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            AssignmentRubric.model_validate({**make_rubric().model_dump(), "student_score": 90})


class TestAssignmentTemplate:
    def test_normalizes_public_ids_and_topic(self) -> None:
        assignment = make_assignment(
            assignment_id=" Cranial-Nerves-Case ",
            topic_id=" Cranial-Nerves ",
            rubric_id=" Neuro-Reasoning ",
        )
        assert assignment.assignment_id == "cranial-nerves-case"
        assert assignment.topic_id == "cranial-nerves"
        assert assignment.rubric_id == "neuro-reasoning"

    def test_rejects_invalid_slug(self) -> None:
        with pytest.raises(ValidationError, match="single hyphens"):
            make_assignment(assignment_id="case_1")

    def test_rejects_duplicate_deliverables(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            make_assignment(deliverables=["Same.", "Same."])

    def test_rejects_empty_deliverables(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            make_assignment(deliverables=[])


class TestCourseAssignmentCatalog:
    def test_enabled_catalog_requires_content(self) -> None:
        with pytest.raises(ValidationError, match="requires assignments and rubrics"):
            make_catalog(assignments=[], rubrics=[])

    def test_disabled_catalog_may_be_empty(self) -> None:
        catalog = make_catalog(enabled=False, assignments=[], rubrics=[])
        assert catalog.assignments == ()

    def test_rejects_duplicate_assignment_ids(self) -> None:
        assignment = make_assignment()
        with pytest.raises(ValidationError, match="repeat an assignment_id"):
            make_catalog(assignments=[assignment, assignment])

    def test_rejects_duplicate_rubric_ids(self) -> None:
        rubric = make_rubric()
        with pytest.raises(ValidationError, match="repeat a rubric_id"):
            make_catalog(rubrics=[rubric, rubric])

    def test_rejects_missing_rubric_reference(self) -> None:
        with pytest.raises(ValidationError, match="unknown rubric"):
            make_catalog(assignments=[make_assignment(rubric_id="missing")])

    def test_finds_assignment_and_rubric_by_normalized_id(self) -> None:
        catalog = make_catalog()
        assert catalog.find_assignment(" Cranial-Nerves-Case ") == make_assignment()
        assert catalog.find_rubric(" Neuro-Reasoning ") == make_rubric()
        assert catalog.find_assignment("another") is None


class TestCatalogAssignmentDraft:
    def test_accepts_aligned_assignment_rubric_and_plan(self) -> None:
        draft = CatalogAssignmentDraft(
            assignment=make_assignment(),
            rubric=make_rubric(),
            plan=make_plan(),
        )
        assert draft.plan.action_type is ClassroomActionType.CREATE_COURSEWORK_DRAFT

    @pytest.mark.parametrize(
        "updates, expected",
        [
            ({"rubric": make_rubric(rubric_id="other")}, "rubric"),
            ({"plan": make_plan(topic_id="motor-system")}, "different topics"),
            ({"plan": make_plan(title="Changed")}, "different titles"),
        ],
    )
    def test_rejects_misaligned_draft(self, updates: dict[str, object], expected: str) -> None:
        values: dict[str, object] = {
            "assignment": make_assignment(),
            "rubric": make_rubric(),
            "plan": make_plan(),
        }
        values.update(updates)
        with pytest.raises(ValidationError, match=expected):
            CatalogAssignmentDraft(**values)  # type: ignore[arg-type]
