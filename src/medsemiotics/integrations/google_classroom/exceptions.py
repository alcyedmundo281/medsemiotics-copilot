"""Exceptions for the Google Classroom Apps Script read boundary."""

from medsemiotics.domain.exceptions import MedSemioticsError


class GoogleClassroomError(MedSemioticsError):
    """Base exception for Google Classroom integration errors."""


class GoogleClassroomConfigurationError(GoogleClassroomError):
    """Raised when the Apps Script deployment configuration is missing or invalid."""


class GoogleClassroomBoundaryError(GoogleClassroomError):
    """Raised when a read is unauthorized or a payload exceeds the metadata-only boundary."""


class GoogleClassroomReadError(GoogleClassroomError):
    """Raised when the Apps Script deployment cannot be reached or returns an unusable reply."""


class GoogleClassroomMappingError(GoogleClassroomError):
    """Raised when a sanitized Apps Script payload fails mapping to domain course metadata."""
