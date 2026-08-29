"""Unit tests for four-C agent capability domain contracts."""

import pytest
from pydantic import ValidationError

from medsemiotics.domain.agents import (
    AgentAuthorizationContext,
    AgentCapability,
    AgentPillar,
    AgentProfile,
    AutonomyLevel,
)


def make_capability(**updates: object) -> AgentCapability:
    """Build a valid read-only capability with optional field overrides."""
    values: dict[str, object] = {
        "capability_id": "clarity.evidence-review",
        "agent": AgentPillar.CLARITY,
        "job": "Review evidence.",
        "tools": ["evidence:read"],
        "categories": ["claims", "sources"],
        "output": "Evidence report.",
        "boundary": "Do not publish.",
        "minimum_autonomy": AutonomyLevel.OBSERVE,
        "maximum_autonomy": AutonomyLevel.RECOMMEND,
    }
    values.update(updates)
    return AgentCapability(**values)  # type: ignore[arg-type]


class TestAutonomyContracts:
    """Validate the progressive autonomy ladder and capability invariants."""

    def test_autonomy_ladder_has_stable_numeric_order(self) -> None:
        assert [level.value for level in AutonomyLevel] == [0, 1, 2, 3, 4]
        assert AutonomyLevel.OBSERVE < AutonomyLevel.TRUSTED_AUTOMATION

    def test_four_agent_pillars_are_complete(self) -> None:
        assert {pillar.value for pillar in AgentPillar} == {
            "coordination",
            "creativity",
            "clarity",
            "coaching",
        }

    def test_valid_capability_is_immutable(self) -> None:
        capability = make_capability()
        assert capability.capability_id == "clarity.evidence-review"
        with pytest.raises(ValidationError):
            capability.job = "Changed"  # type: ignore[misc]

    def test_external_mutation_cannot_start_below_approval_level(self) -> None:
        with pytest.raises(ValidationError, match="external mutation capabilities must start"):
            make_capability(
                external_mutation=True,
                minimum_autonomy=AutonomyLevel.DRAFT,
                maximum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
            )

    def test_inverted_autonomy_range_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="minimum_autonomy must not exceed"):
            make_capability(
                minimum_autonomy=AutonomyLevel.DRAFT,
                maximum_autonomy=AutonomyLevel.RECOMMEND,
            )

    def test_trusted_automation_requires_level_four_ceiling(self) -> None:
        with pytest.raises(ValidationError, match="eligibility requires maximum_autonomy"):
            make_capability(trusted_automation_eligible=True)

    def test_duplicate_tools_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="tools contains duplicate"):
            make_capability(tools=["evidence:read", "evidence:read"])

    def test_non_namespaced_capability_id_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="lower-case namespaced"):
            make_capability(capability_id="EvidenceReview")


class TestAgentProfileAndApproval:
    """Validate profile ownership and accountable approval evidence."""

    def test_profile_rejects_capability_from_another_agent(self) -> None:
        capability = make_capability()
        with pytest.raises(ValidationError, match="belongs to clarity, not coaching"):
            AgentProfile(
                agent=AgentPillar.COACHING,
                purpose="Coach teaching.",
                maximum_autonomy=AutonomyLevel.DRAFT,
                capabilities=[capability],
            )

    def test_profile_rejects_capability_above_agent_ceiling(self) -> None:
        capability = make_capability(maximum_autonomy=AutonomyLevel.RECOMMEND)
        with pytest.raises(ValidationError, match="exceeds the clarity agent autonomy ceiling"):
            AgentProfile(
                agent=AgentPillar.CLARITY,
                purpose="Review evidence.",
                maximum_autonomy=AutonomyLevel.OBSERVE,
                capabilities=[capability],
            )

    def test_profile_rejects_duplicate_capability_ids(self) -> None:
        capability = make_capability()
        with pytest.raises(ValidationError, match="Duplicate capability_id"):
            AgentProfile(
                agent=AgentPillar.CLARITY,
                purpose="Review evidence.",
                maximum_autonomy=AutonomyLevel.RECOMMEND,
                capabilities=[capability, capability],
            )

    def test_approval_requires_named_approver(self) -> None:
        with pytest.raises(ValidationError, match="approved=True requires approved_by"):
            AgentAuthorizationContext(approved=True)

    def test_approver_cannot_exist_without_approval(self) -> None:
        with pytest.raises(ValidationError, match="approved_by requires approved=True"):
            AgentAuthorizationContext(approved_by="operator")
