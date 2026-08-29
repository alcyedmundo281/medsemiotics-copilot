"""Tests for the minimal Loop 0.6A Google Classroom access contract."""

import pytest
from pydantic import ValidationError

from medsemiotics.agents.framework import build_default_agent_framework
from medsemiotics.domain.agents import AgentPillar, AutonomyLevel
from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    ClassroomAccessRequest,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.exceptions import ClassroomAccessPolicyError
from medsemiotics.services.classroom_access_policy import ClassroomAccessPolicy


def make_request(**updates: object) -> ClassroomAccessRequest:
    """Build the only access request permitted by Loop 0.6A."""
    values: dict[str, object] = {
        "operation": ClassroomOperation.COURSE_DISCOVERY,
        "data_categories": [ClassroomDataCategory.COURSE_METADATA],
        "oauth_scopes": [GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE],
        "requested_by": "course-director",
        "external_mutation": False,
    }
    values.update(updates)
    return ClassroomAccessRequest(**values)  # type: ignore[arg-type]


class TestClassroomAccessPolicy:
    """Verify the policy permits only minimal, metadata-only course discovery."""

    def test_allows_exact_read_only_course_discovery(self) -> None:
        decision = ClassroomAccessPolicy().authorize(make_request())

        assert decision.allowed is True
        assert decision.approved_data_categories == (ClassroomDataCategory.COURSE_METADATA,)
        assert decision.approved_oauth_scopes == (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)

    @pytest.mark.parametrize(
        "prohibited_category",
        [
            ClassroomDataCategory.ROSTERS,
            ClassroomDataCategory.STUDENT_IDENTIFIERS,
            ClassroomDataCategory.COURSEWORK,
            ClassroomDataCategory.SUBMISSIONS,
            ClassroomDataCategory.GRADES,
        ],
    )
    def test_denies_sensitive_or_student_level_categories(
        self,
        prohibited_category: ClassroomDataCategory,
    ) -> None:
        request = make_request(
            data_categories=[ClassroomDataCategory.COURSE_METADATA, prohibited_category]
        )

        decision = ClassroomAccessPolicy().evaluate(request)

        assert decision.allowed is False
        assert decision.approved_data_categories == ()
        assert prohibited_category.value in {
            "rosters",
            "student_identifiers",
            "coursework",
            "submissions",
            "grades",
        }

    def test_denies_mutation_before_any_adapter_runs(self) -> None:
        request = make_request(external_mutation=True)

        with pytest.raises(ClassroomAccessPolicyError, match="read-only"):
            ClassroomAccessPolicy().authorize(request)

    @pytest.mark.parametrize(
        "scopes",
        [
            ["https://www.googleapis.com/auth/classroom.courses"],
            [
                GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
                "https://www.googleapis.com/auth/classroom.rosters.readonly",
            ],
        ],
    )
    def test_denies_broader_or_additional_oauth_scopes(self, scopes: list[str]) -> None:
        decision = ClassroomAccessPolicy().evaluate(make_request(oauth_scopes=scopes))

        assert decision.allowed is False
        assert decision.approved_oauth_scopes == ()
        assert "exactly" in decision.reason

    def test_rejects_duplicate_permission_declarations(self) -> None:
        with pytest.raises(ValidationError, match="must not contain duplicate"):
            make_request(
                oauth_scopes=[
                    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
                    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
                ]
            )

    def test_rejects_unordered_permission_declarations(self) -> None:
        with pytest.raises(ValidationError, match="ordered list or tuple"):
            make_request(data_categories={ClassroomDataCategory.COURSE_METADATA})

    @pytest.mark.parametrize("field_name", ["data_categories", "oauth_scopes"])
    def test_rejects_empty_permission_declarations(self, field_name: str) -> None:
        with pytest.raises(ValidationError, match="must contain at least one item"):
            make_request(**{field_name: []})

    def test_requires_accountable_requester(self) -> None:
        with pytest.raises(ValidationError, match="requested_by must not be empty"):
            make_request(requested_by="  ")

    def test_rejects_hidden_extra_controls(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ClassroomAccessRequest.model_validate(
                {**make_request().model_dump(), "include_students": True}
            )


def test_default_agent_framework_declares_classroom_discovery_as_observe_only() -> None:
    """Verify the Coordination agent cannot expand discovery into a write capability."""
    capability = build_default_agent_framework().get_capability(
        AgentPillar.COORDINATION,
        "coordination.classroom-course-discovery",
    )

    assert capability.minimum_autonomy == AutonomyLevel.OBSERVE
    assert capability.maximum_autonomy == AutonomyLevel.OBSERVE
    assert capability.external_mutation is False
    assert capability.trusted_automation_eligible is False
    assert capability.tools == ["google-classroom:courses.readonly"]
