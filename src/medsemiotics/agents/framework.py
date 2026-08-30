"""Deterministic capability catalog and authorization policy for the four-C agents."""

from collections.abc import Iterable

from medsemiotics.domain.agents import (
    AgentActionIntent,
    AgentAuthorizationContext,
    AgentCapability,
    AgentCapabilityDecision,
    AgentPillar,
    AgentProfile,
    AutonomyLevel,
)
from medsemiotics.domain.exceptions import (
    AgentAuthorizationError,
    AgentCapabilityConfigurationError,
)


class AgentCapabilityFramework:
    """Read-only capability registry with deterministic authorization decisions."""

    def __init__(self, profiles: Iterable[AgentProfile]) -> None:
        """Index validated profiles and reject ambiguous registrations."""
        self._profiles: dict[AgentPillar, AgentProfile] = {}
        self._capabilities: dict[tuple[AgentPillar, str], AgentCapability] = {}

        for profile in profiles:
            if profile.agent in self._profiles:
                msg = f"Duplicate agent profile '{profile.agent.value}'"
                raise AgentCapabilityConfigurationError(msg)
            self._profiles[profile.agent] = profile

            for capability in profile.capabilities:
                key = (profile.agent, capability.capability_id)
                if key in self._capabilities:
                    msg = f"Duplicate capability registration '{capability.capability_id}'"
                    raise AgentCapabilityConfigurationError(msg)
                self._capabilities[key] = capability

        if not self._profiles:
            msg = "At least one agent profile is required"
            raise AgentCapabilityConfigurationError(msg)

    def list_profiles(self) -> tuple[AgentProfile, ...]:
        """Return profiles in stable four-C enumeration order."""
        return tuple(self._profiles[agent] for agent in AgentPillar if agent in self._profiles)

    def get_profile(self, agent: AgentPillar) -> AgentProfile:
        """Resolve an agent profile or raise a configuration error."""
        try:
            return self._profiles[agent]
        except KeyError as err:
            msg = f"Agent profile '{agent.value}' is not registered"
            raise AgentCapabilityConfigurationError(msg) from err

    def get_capability(self, agent: AgentPillar, capability_id: str) -> AgentCapability:
        """Resolve a capability within its owning agent scope."""
        try:
            return self._capabilities[(agent, capability_id)]
        except KeyError as err:
            msg = f"Capability '{capability_id}' is not registered for {agent.value}"
            raise AgentCapabilityConfigurationError(msg) from err

    def evaluate(
        self,
        intent: AgentActionIntent,
        context: AgentAuthorizationContext | None = None,
    ) -> AgentCapabilityDecision:
        """Evaluate an intent without executing tools or producing side effects."""
        authorization = context or AgentAuthorizationContext()
        profile = self.get_profile(intent.agent)
        capability = self.get_capability(intent.agent, intent.capability_id)

        if intent.requested_autonomy < capability.minimum_autonomy:
            return self._decision(
                intent,
                allowed=False,
                requires_approval=False,
                reason=(
                    f"Capability requires at least {capability.minimum_autonomy.name}; "
                    f"requested {intent.requested_autonomy.name}."
                ),
            )

        ceiling = min(profile.maximum_autonomy, capability.maximum_autonomy)
        if intent.requested_autonomy > ceiling:
            return self._decision(
                intent,
                allowed=False,
                requires_approval=False,
                reason=(
                    f"Requested autonomy {intent.requested_autonomy.name} exceeds "
                    f"the permitted ceiling {ceiling.name}."
                ),
            )

        if intent.requested_autonomy == AutonomyLevel.EXECUTE_WITH_APPROVAL:
            if not authorization.approved:
                return self._decision(
                    intent,
                    allowed=False,
                    requires_approval=True,
                    reason="Execution requires explicit human approval.",
                )
            return self._decision(
                intent,
                allowed=True,
                requires_approval=False,
                reason=f"Execution approved by {authorization.approved_by}.",
            )

        if intent.requested_autonomy == AutonomyLevel.TRUSTED_AUTOMATION:
            if not capability.trusted_automation_eligible:
                return self._decision(
                    intent,
                    allowed=False,
                    requires_approval=False,
                    reason="Capability is not eligible for trusted automation.",
                )
            if not authorization.trusted_automation_enabled:
                return self._decision(
                    intent,
                    allowed=False,
                    requires_approval=False,
                    reason="Trusted automation is not enabled for this execution context.",
                )
            return self._decision(
                intent,
                allowed=True,
                requires_approval=False,
                reason="Narrow trusted automation policy is enabled.",
            )

        return self._decision(
            intent,
            allowed=True,
            requires_approval=False,
            reason=f"{intent.requested_autonomy.name} is within the declared capability range.",
        )

    def authorize(
        self,
        intent: AgentActionIntent,
        context: AgentAuthorizationContext | None = None,
    ) -> AgentCapabilityDecision:
        """Return an allowed decision or raise before any caller reaches an ACT adapter."""
        decision = self.evaluate(intent, context)
        if not decision.allowed:
            msg = (
                f"Agent action denied for '{decision.capability_id}' at "
                f"{decision.requested_autonomy.name}: {decision.reason}"
            )
            raise AgentAuthorizationError(msg)
        return decision

    @staticmethod
    def _decision(
        intent: AgentActionIntent,
        *,
        allowed: bool,
        requires_approval: bool,
        reason: str,
    ) -> AgentCapabilityDecision:
        """Build a consistent immutable policy decision."""
        return AgentCapabilityDecision(
            allowed=allowed,
            agent=intent.agent,
            capability_id=intent.capability_id,
            requested_autonomy=intent.requested_autonomy,
            requires_approval=requires_approval,
            reason=reason,
        )


def build_default_agent_framework() -> AgentCapabilityFramework:
    """Build the Loop 0.5A four-C catalog without any LLM or live tool binding."""
    return AgentCapabilityFramework(
        profiles=[
            AgentProfile(
                agent=AgentPillar.COORDINATION,
                purpose="Align academic state, schedules, tasks, and preparation priorities.",
                maximum_autonomy=AutonomyLevel.TRUSTED_AUTOMATION,
                capabilities=[
                    AgentCapability(
                        capability_id="coordination.classroom-course-discovery",
                        agent=AgentPillar.COORDINATION,
                        job="Discover accessible Classroom courses using metadata only.",
                        tools=["google-classroom:courses.readonly"],
                        categories=["course metadata", "course state", "course link"],
                        output="Sanitized provider-neutral course discovery result.",
                        boundary=(
                            "Must not expose rosters, student identifiers, coursework, "
                            "submissions, grades, or execute any Classroom mutation."
                        ),
                        minimum_autonomy=AutonomyLevel.OBSERVE,
                        maximum_autonomy=AutonomyLevel.OBSERVE,
                    ),
                    AgentCapability(
                        capability_id="coordination.course-coordination-view",
                        agent=AgentPillar.COORDINATION,
                        job=(
                            "Compose a read-only coordination view across Classroom, Calendar, "
                            "and academic state."
                        ),
                        tools=[
                            "classroom-snapshot:read",
                            "calendar-config:read",
                            "academic-state:read",
                        ],
                        categories=[
                            "classroom binding",
                            "calendar binding",
                            "academic progress",
                            "coordination gaps",
                        ],
                        output="Explainable per-course coordination view with recorded gaps.",
                        boundary=(
                            "Must not expose student data, contact any provider, or mutate "
                            "Classroom or Calendar."
                        ),
                        minimum_autonomy=AutonomyLevel.OBSERVE,
                        maximum_autonomy=AutonomyLevel.OBSERVE,
                    ),
                    AgentCapability(
                        capability_id="coordination.daily-brief",
                        agent=AgentPillar.COORDINATION,
                        job="Prepare a prioritized daily academic coordination brief.",
                        tools=["academic-state:read", "google-calendar:read"],
                        categories=["conflicts", "preparation", "priorities", "deferrable work"],
                        output="Structured daily coordination brief.",
                        boundary="Must not create, move, or delete calendar events.",
                        minimum_autonomy=AutonomyLevel.OBSERVE,
                        maximum_autonomy=AutonomyLevel.TRUSTED_AUTOMATION,
                        trusted_automation_eligible=True,
                    ),
                    AgentCapability(
                        capability_id="coordination.classroom-action",
                        agent=AgentPillar.COORDINATION,
                        job="Execute one explicitly approved, idempotent Classroom action.",
                        tools=["google-classroom:coursework-draft"],
                        categories=["target course", "planned action", "named approval"],
                        output="Audited single Classroom action decision.",
                        boundary=(
                            "Must not publish grades, write to students, execute more than one "
                            "action, or run without a named approval of the reviewed content."
                        ),
                        minimum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                        maximum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                        external_mutation=True,
                    ),
                    AgentCapability(
                        capability_id="coordination.calendar-publish",
                        agent=AgentPillar.COORDINATION,
                        job="Publish one explicitly approved academic calendar action.",
                        tools=["google-calendar:write"],
                        categories=["target event", "ownership", "approved change"],
                        output="Audited calendar publication result.",
                        boundary=(
                            "Must not mutate unowned events, bulk publish, or execute without "
                            "human approval."
                        ),
                        minimum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                        maximum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                        external_mutation=True,
                    ),
                ],
            ),
            AgentProfile(
                agent=AgentPillar.CREATIVITY,
                purpose="Turn source material into reviewable teaching and publication drafts.",
                maximum_autonomy=AutonomyLevel.DRAFT,
                capabilities=[
                    AgentCapability(
                        capability_id="creativity.teaching-material-draft",
                        agent=AgentPillar.CREATIVITY,
                        job="Create a teaching artifact draft from supplied academic sources.",
                        tools=["local-sources:read", "artifact-workspace:draft"],
                        categories=["audience", "learning goal", "format", "voice"],
                        output="Reviewable teaching material draft.",
                        boundary="Must not publish, distribute, or overwrite an approved artifact.",
                        minimum_autonomy=AutonomyLevel.DRAFT,
                        maximum_autonomy=AutonomyLevel.DRAFT,
                    )
                ],
            ),
            AgentProfile(
                agent=AgentPillar.CLARITY,
                purpose="Inspect evidence and assessments at panoramic or item-level depth.",
                maximum_autonomy=AutonomyLevel.RECOMMEND,
                capabilities=[
                    AgentCapability(
                        capability_id="clarity.evidence-review",
                        agent=AgentPillar.CLARITY,
                        job="Synthesize or inspect medical evidence with traceable sources.",
                        tools=["evidence-catalog:read", "academic-content:read"],
                        categories=["claims", "sources", "uncertainty", "gaps"],
                        output="Evidence review with explicit limitations.",
                        boundary="Must not invent sources or publish medical claims.",
                        minimum_autonomy=AutonomyLevel.OBSERVE,
                        maximum_autonomy=AutonomyLevel.RECOMMEND,
                    ),
                    AgentCapability(
                        capability_id="clarity.assessment-analysis",
                        agent=AgentPillar.CLARITY,
                        job="Analyze an assessment or item without changing grades.",
                        tools=["assessment-data:read"],
                        categories=["difficulty", "discrimination", "distractors", "alignment"],
                        output="Assessment analysis and recommendations.",
                        boundary="Must not identify students, alter grades, or release results.",
                        minimum_autonomy=AutonomyLevel.OBSERVE,
                        maximum_autonomy=AutonomyLevel.RECOMMEND,
                    ),
                ],
            ),
            AgentProfile(
                agent=AgentPillar.COACHING,
                purpose="Prepare and improve teaching through bounded pedagogical coaching.",
                maximum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                capabilities=[
                    AgentCapability(
                        capability_id="coaching.class-brief",
                        agent=AgentPillar.COACHING,
                        job="Prepare a pedagogical briefing for one upcoming class.",
                        tools=[
                            "academic-state:read",
                            "effective-schedule:read",
                            "evidence-catalog:read",
                        ],
                        categories=[
                            "objectives",
                            "critical points",
                            "misconceptions",
                            "questions",
                            "materials",
                        ],
                        output="Structured CoachingBrief draft.",
                        boundary="Must not publish the brief or modify the teaching schedule.",
                        minimum_autonomy=AutonomyLevel.RECOMMEND,
                        maximum_autonomy=AutonomyLevel.DRAFT,
                    ),
                    AgentCapability(
                        capability_id="coaching.calendar-brief-publish",
                        agent=AgentPillar.COACHING,
                        job="Publish one approved CoachingBrief to an owned class event.",
                        tools=["google-calendar:write"],
                        categories=["approved brief", "owned event", "publication result"],
                        output="Audited CalendarPublishResult.",
                        boundary=(
                            "Must preserve Calendar ownership gates and requires separate "
                            "per-action approval."
                        ),
                        minimum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                        maximum_autonomy=AutonomyLevel.EXECUTE_WITH_APPROVAL,
                        external_mutation=True,
                    ),
                ],
            ),
        ]
    )
