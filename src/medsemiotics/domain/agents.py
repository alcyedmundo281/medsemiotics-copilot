"""Domain contracts for the MedSemiotics four-agent capability framework."""

from enum import IntEnum, StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentPillar(StrEnum):
    """The four specialized agent pillars used by MedSemiotics."""

    COORDINATION = "coordination"
    CREATIVITY = "creativity"
    CLARITY = "clarity"
    COACHING = "coaching"


class AutonomyLevel(IntEnum):
    """Progressive autonomy ladder; higher levels require stronger trust controls."""

    OBSERVE = 0
    RECOMMEND = 1
    DRAFT = 2
    EXECUTE_WITH_APPROVAL = 3
    TRUSTED_AUTOMATION = 4


def _clean_required_text(value: object, field_name: str) -> str:
    """Normalize a required text field and reject blank values."""
    if not isinstance(value, str):
        msg = f"{field_name} must be a string, got {type(value).__name__}"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = f"{field_name} must not be empty or whitespace only"
        raise ValueError(msg)
    return cleaned


def _clean_unique_strings(value: object, field_name: str) -> list[str]:
    """Normalize a non-empty string list while preserving its declared order."""
    if not isinstance(value, list):
        msg = f"{field_name} must be a list of strings, got {type(value).__name__}"
        raise ValueError(msg)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _clean_required_text(item, f"{field_name} item")
        if normalized in seen:
            msg = f"{field_name} contains duplicate value '{normalized}'"
            raise ValueError(msg)
        seen.add(normalized)
        cleaned.append(normalized)

    if not cleaned:
        msg = f"{field_name} must contain at least one item"
        raise ValueError(msg)
    return cleaned


class AgentCapability(BaseModel):
    """A bounded job an agent may perform within a declared autonomy range."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability_id: Annotated[str, Field(description="Stable namespaced capability identifier")]
    agent: Annotated[AgentPillar, Field(description="Owning four-C agent pillar")]
    job: Annotated[str, Field(description="Concrete job assigned to the capability")]
    tools: Annotated[list[str], Field(description="Tools or data sources the job may use")]
    categories: Annotated[list[str], Field(description="Required analysis or output categories")]
    output: Annotated[str, Field(description="Expected structured deliverable")]
    boundary: Annotated[str, Field(description="Explicitly prohibited behavior")]
    minimum_autonomy: Annotated[
        AutonomyLevel, Field(description="Lowest autonomy level at which the job is meaningful")
    ]
    maximum_autonomy: Annotated[
        AutonomyLevel, Field(description="Highest autonomy level currently permitted")
    ]
    external_mutation: Annotated[
        bool, Field(description="Whether the job can mutate an external system")
    ] = False
    trusted_automation_eligible: Annotated[
        bool,
        Field(
            description="Whether a separately enabled policy may run this job at level 4",
        ),
    ] = False

    @field_validator("capability_id", mode="before")
    @classmethod
    def validate_capability_id(cls, value: object) -> str:
        """Require a stable lower-case namespaced identifier."""
        cleaned = _clean_required_text(value, "capability_id")
        if cleaned != cleaned.lower() or "." not in cleaned:
            msg = "capability_id must be a lower-case namespaced identifier"
            raise ValueError(msg)
        valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-._")
        if any(char not in valid_chars for char in cleaned):
            msg = "capability_id contains unsupported characters"
            raise ValueError(msg)
        return cleaned

    @field_validator("job", "output", "boundary", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        """Normalize required descriptive fields."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)

    @field_validator("tools", "categories", mode="before")
    @classmethod
    def validate_string_lists(cls, value: object, info: object) -> list[str]:
        """Require non-empty, duplicate-free tool and category lists."""
        field_name = getattr(info, "field_name", "list field")
        return _clean_unique_strings(value, field_name)

    @model_validator(mode="after")
    def validate_autonomy_contract(self) -> "AgentCapability":
        """Enforce range, write-safety, and trusted-automation invariants."""
        if self.minimum_autonomy > self.maximum_autonomy:
            msg = "minimum_autonomy must not exceed maximum_autonomy"
            raise ValueError(msg)

        if self.external_mutation and self.minimum_autonomy < AutonomyLevel.EXECUTE_WITH_APPROVAL:
            msg = "external mutation capabilities must start at EXECUTE_WITH_APPROVAL"
            raise ValueError(msg)

        if (
            self.trusted_automation_eligible
            and self.maximum_autonomy < AutonomyLevel.TRUSTED_AUTOMATION
        ):
            msg = "trusted automation eligibility requires maximum_autonomy TRUSTED_AUTOMATION"
            raise ValueError(msg)

        return self


class AgentProfile(BaseModel):
    """Declared purpose, ceiling, and bounded capabilities for one four-C agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: AgentPillar
    purpose: str
    maximum_autonomy: AutonomyLevel
    capabilities: list[AgentCapability]

    @field_validator("purpose", mode="before")
    @classmethod
    def validate_purpose(cls, value: object) -> str:
        """Normalize the agent purpose."""
        return _clean_required_text(value, "purpose")

    @field_validator("capabilities", mode="before")
    @classmethod
    def validate_capabilities_collection(cls, value: object) -> object:
        """Reject missing or empty capability declarations."""
        if not isinstance(value, list) or not value:
            msg = "capabilities must contain at least one capability"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_capability_scope(self) -> "AgentProfile":
        """Ensure capability ownership, ceilings, and identifiers are coherent."""
        seen: set[str] = set()
        for capability in self.capabilities:
            if capability.agent != self.agent:
                msg = (
                    f"Capability '{capability.capability_id}' belongs to {capability.agent.value}, "
                    f"not {self.agent.value}"
                )
                raise ValueError(msg)
            if capability.maximum_autonomy > self.maximum_autonomy:
                msg = (
                    f"Capability '{capability.capability_id}' exceeds the "
                    f"{self.agent.value} agent autonomy ceiling"
                )
                raise ValueError(msg)
            if capability.capability_id in seen:
                msg = f"Duplicate capability_id '{capability.capability_id}'"
                raise ValueError(msg)
            seen.add(capability.capability_id)
        return self


class AgentActionIntent(BaseModel):
    """Auditable request to use one capability at a specific autonomy level."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: AgentPillar
    capability_id: str
    requested_autonomy: AutonomyLevel
    requested_by: str
    rationale: str

    @field_validator("capability_id", "requested_by", "rationale", mode="before")
    @classmethod
    def validate_required_strings(cls, value: object, info: object) -> str:
        """Normalize required audit fields."""
        field_name = getattr(info, "field_name", "field")
        return _clean_required_text(value, field_name)


class AgentAuthorizationContext(BaseModel):
    """Human approval or narrow trusted-automation state for one policy decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    approved: bool = False
    approved_by: str | None = None
    trusted_automation_enabled: bool = False

    @field_validator("approved_by", mode="before")
    @classmethod
    def validate_approver(cls, value: object) -> str | None:
        """Normalize the optional approver identity."""
        if value is None:
            return None
        return _clean_required_text(value, "approved_by")

    @model_validator(mode="after")
    def validate_approval_evidence(self) -> "AgentAuthorizationContext":
        """An approval flag is invalid without an accountable approver."""
        if self.approved and self.approved_by is None:
            msg = "approved=True requires approved_by"
            raise ValueError(msg)
        if not self.approved and self.approved_by is not None:
            msg = "approved_by requires approved=True"
            raise ValueError(msg)
        return self


class AgentCapabilityDecision(BaseModel):
    """Deterministic result of evaluating an agent action intent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    agent: AgentPillar
    capability_id: str
    requested_autonomy: AutonomyLevel
    requires_approval: bool
    reason: str
