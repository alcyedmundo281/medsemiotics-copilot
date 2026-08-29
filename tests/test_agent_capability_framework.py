"""Tests for deterministic four-C capability registration and authorization policy."""

import pytest

from medsemiotics.agents.framework import (
    AgentCapabilityFramework,
    build_default_agent_framework,
)
from medsemiotics.domain.agents import (
    AgentActionIntent,
    AgentAuthorizationContext,
    AgentPillar,
    AutonomyLevel,
)
from medsemiotics.domain.exceptions import (
    AgentAuthorizationError,
    AgentCapabilityConfigurationError,
)


def make_intent(
    agent: AgentPillar,
    capability_id: str,
    autonomy: AutonomyLevel,
) -> AgentActionIntent:
    """Build a complete auditable intent for policy tests."""
    return AgentActionIntent(
        agent=agent,
        capability_id=capability_id,
        requested_autonomy=autonomy,
        requested_by="test-operator",
        rationale="Verify policy boundary.",
    )


@pytest.fixture
def framework() -> AgentCapabilityFramework:
    return build_default_agent_framework()


class TestDefaultCatalog:
    """Verify Loop 0.5A registers all four bounded agent profiles."""

    def test_catalog_contains_exactly_the_four_c_agents(
        self, framework: AgentCapabilityFramework
    ) -> None:
        assert [profile.agent for profile in framework.list_profiles()] == list(AgentPillar)

    def test_framework_is_deterministic_and_has_no_runtime_provider(
        self, framework: AgentCapabilityFramework
    ) -> None:
        coaching = framework.get_profile(AgentPillar.COACHING)
        assert coaching.purpose
        assert all(capability.tools for capability in coaching.capabilities)

    def test_all_external_mutations_require_approval_and_are_not_trusted(
        self, framework: AgentCapabilityFramework
    ) -> None:
        mutating = [
            capability
            for profile in framework.list_profiles()
            for capability in profile.capabilities
            if capability.external_mutation
        ]
        assert mutating
        assert all(
            capability.minimum_autonomy == AutonomyLevel.EXECUTE_WITH_APPROVAL
            for capability in mutating
        )
        assert all(not capability.trusted_automation_eligible for capability in mutating)

    def test_unknown_capability_is_configuration_error(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.COACHING,
            "coaching.unknown",
            AutonomyLevel.OBSERVE,
        )
        with pytest.raises(AgentCapabilityConfigurationError, match="not registered"):
            framework.evaluate(intent)


class TestAuthorizationPolicy:
    """Verify promotion gates from observe through trusted automation."""

    def test_coaching_draft_is_allowed_without_acting(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.COACHING,
            "coaching.class-brief",
            AutonomyLevel.DRAFT,
        )
        decision = framework.evaluate(intent)
        assert decision.allowed is True
        assert decision.requires_approval is False

    def test_mutation_is_denied_without_human_approval(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.COACHING,
            "coaching.calendar-brief-publish",
            AutonomyLevel.EXECUTE_WITH_APPROVAL,
        )
        decision = framework.evaluate(intent)
        assert decision.allowed is False
        assert decision.requires_approval is True
        assert "explicit human approval" in decision.reason

    def test_mutation_is_allowed_with_named_human_approval(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.COACHING,
            "coaching.calendar-brief-publish",
            AutonomyLevel.EXECUTE_WITH_APPROVAL,
        )
        context = AgentAuthorizationContext(approved=True, approved_by="course-director")
        decision = framework.authorize(intent, context)
        assert decision.allowed is True
        assert "course-director" in decision.reason

    def test_authorize_raises_before_act_on_denial(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.COORDINATION,
            "coordination.calendar-publish",
            AutonomyLevel.EXECUTE_WITH_APPROVAL,
        )
        with pytest.raises(AgentAuthorizationError, match="Agent action denied"):
            framework.authorize(intent)

    def test_request_below_capability_minimum_is_denied(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.CREATIVITY,
            "creativity.teaching-material-draft",
            AutonomyLevel.RECOMMEND,
        )
        decision = framework.evaluate(intent)
        assert decision.allowed is False
        assert "requires at least DRAFT" in decision.reason

    def test_request_above_capability_ceiling_is_denied(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.CLARITY,
            "clarity.evidence-review",
            AutonomyLevel.DRAFT,
        )
        decision = framework.evaluate(intent)
        assert decision.allowed is False
        assert "exceeds the permitted ceiling" in decision.reason

    def test_trusted_daily_brief_requires_separate_policy_enablement(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.COORDINATION,
            "coordination.daily-brief",
            AutonomyLevel.TRUSTED_AUTOMATION,
        )
        assert framework.evaluate(intent).allowed is False

        enabled = AgentAuthorizationContext(trusted_automation_enabled=True)
        assert framework.evaluate(intent, enabled).allowed is True

    def test_calendar_mutation_cannot_be_promoted_to_trusted_automation(
        self, framework: AgentCapabilityFramework
    ) -> None:
        intent = make_intent(
            AgentPillar.COORDINATION,
            "coordination.calendar-publish",
            AutonomyLevel.TRUSTED_AUTOMATION,
        )
        context = AgentAuthorizationContext(trusted_automation_enabled=True)
        decision = framework.evaluate(intent, context)
        assert decision.allowed is False
        assert "permitted ceiling" in decision.reason
