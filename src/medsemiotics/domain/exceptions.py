"""Domain-level exceptions for MedSemiotics Teaching Copilot."""


class MedSemioticsError(Exception):
    """Base exception for all MedSemiotics domain and service errors."""


class SemesterConfigError(MedSemioticsError):
    """Base exception for semester configuration errors."""


class SemesterConfigNotFoundError(SemesterConfigError):
    """Raised when a specified semester configuration file or pointer cannot be found."""


class SemesterConfigValidationError(SemesterConfigError):
    """Raised when a semester configuration fails schema or structural validation."""


class SyllabusError(MedSemioticsError):
    """Base exception for syllabus planning errors."""


class SyllabusNotFoundError(SyllabusError):
    """Raised when a syllabus plan file cannot be found."""


class SyllabusValidationError(SyllabusError):
    """Raised when a syllabus plan fails schema, structural, or referential validation."""


class TeachingLogError(MedSemioticsError):
    """Base exception for teaching log errors."""


class TeachingLogNotFoundError(TeachingLogError):
    """Raised when a teaching log file cannot be found."""


class TeachingLogValidationError(TeachingLogError):
    """Raised when a teaching log fails schema or structural validation."""


class AcademicValidationError(MedSemioticsError):
    """Raised when cross-domain referential validation fails."""


class AcademicStateError(MedSemioticsError):
    """Raised when academic state projection fails or scope mismatches."""


class ScheduleError(MedSemioticsError):
    """Base exception for schedule configuration and repository errors."""


class ScheduleNotFoundError(ScheduleError):
    """Raised when a teaching schedule file cannot be found."""


class ScheduleValidationError(ScheduleError):
    """Raised when a teaching schedule fails schema or structural validation."""


class CalendarConfigError(MedSemioticsError):
    """Base exception for calendar configuration and repository errors."""


class CalendarConfigNotFoundError(CalendarConfigError):
    """Raised when a course calendar configuration file cannot be found."""


class CalendarConfigValidationError(CalendarConfigError):
    """Raised when a course calendar configuration fails validation."""


class EffectiveScheduleError(MedSemioticsError):
    """Base exception for effective teaching schedule errors."""


class EffectiveScheduleAmbiguityError(EffectiveScheduleError):
    """Raised when ambiguous or conflicting calendar evidence occurs on the same date."""


class CalendarPublishPlanError(MedSemioticsError):
    """Raised when constructing a calendar publish request fails validation or requirements."""


class CalendarWriteAuthorizationError(MedSemioticsError):
    """Raised when a calendar write action is attempted without explicit authorization."""


class AgentCapabilityError(MedSemioticsError):
    """Base exception for agent capability registration and policy errors."""


class AgentCapabilityConfigurationError(AgentCapabilityError):
    """Raised when the agent capability registry is missing or ambiguous."""


class AgentAuthorizationError(AgentCapabilityError):
    """Raised when an agent intent is outside its declared autonomy boundary."""


class TeachingCoachError(MedSemioticsError):
    """Base exception for Teaching Coach draft preparation errors."""


class TeachingCoachNoClassError(TeachingCoachError):
    """Raised when a briefing is requested for a date without an active effective class."""


class TeachingCoachTopicError(TeachingCoachError):
    """Raised when the curated guide does not match the authoritative current topic."""


class TeachingCoachScopeError(TeachingCoachError):
    """Raised when a read-only dependency returns state from another academic scope."""


class TeachingGuideError(MedSemioticsError):
    """Base exception for curated Teaching Coach guide storage errors."""


class TeachingGuideNotFoundError(TeachingGuideError):
    """Raised when a guide catalog or requested topic guide does not exist."""


class TeachingGuideValidationError(TeachingGuideError):
    """Raised when a curated guide catalog is malformed or inconsistent."""


class TeachingGuideDisabledError(TeachingGuideError):
    """Raised when guide retrieval is attempted from a disabled catalog."""
