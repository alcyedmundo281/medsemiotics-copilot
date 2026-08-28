"""Domain-level exceptions for MedSemiotics Teaching Copilot."""


class MedSemioticsError(Exception):
    """Base exception for all MedSemiotics domain and service errors."""


class SemesterConfigError(MedSemioticsError):
    """Base exception for semester configuration errors."""


class SemesterConfigNotFoundError(SemesterConfigError):
    """Raised when a specified semester configuration file or pointer cannot be found."""


class SemesterConfigValidationError(SemesterConfigError):
    """Raised when a semester configuration fails schema or structural validation."""
