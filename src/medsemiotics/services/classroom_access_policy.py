"""Deterministic data-minimization and OAuth policy for Google Classroom access."""

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    ClassroomAccessDecision,
    ClassroomAccessRequest,
    ClassroomDataCategory,
)
from medsemiotics.domain.exceptions import ClassroomAccessPolicyError


class ClassroomAccessPolicy:
    """Authorize only the narrow 0.6A course-discovery read contract."""

    _ALLOWED_CATEGORIES = (ClassroomDataCategory.COURSE_METADATA,)
    _ALLOWED_SCOPES = (GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,)

    def evaluate(self, request: ClassroomAccessRequest) -> ClassroomAccessDecision:
        """Evaluate one request without calling Google or mutating any external state."""
        if request.external_mutation:
            return self._deny(request, "Course discovery is read-only and cannot mutate Classroom.")
        if request.data_categories != self._ALLOWED_CATEGORIES:
            return self._deny(
                request,
                "Only course_metadata is permitted; rosters, student identifiers, coursework, "
                "submissions, and grades are prohibited.",
            )
        if request.oauth_scopes != self._ALLOWED_SCOPES:
            return self._deny(
                request,
                "Course discovery requires exactly the classroom.courses.readonly OAuth scope.",
            )
        return ClassroomAccessDecision(
            allowed=True,
            operation=request.operation,
            approved_data_categories=self._ALLOWED_CATEGORIES,
            approved_oauth_scopes=self._ALLOWED_SCOPES,
            reason="Minimal read-only course discovery is permitted.",
        )

    def authorize(self, request: ClassroomAccessRequest) -> ClassroomAccessDecision:
        """Return an allowed decision or fail before an integration adapter may execute."""
        decision = self.evaluate(request)
        if not decision.allowed:
            msg = f"Classroom access denied for '{request.operation.value}': {decision.reason}"
            raise ClassroomAccessPolicyError(msg)
        return decision

    @staticmethod
    def _deny(
        request: ClassroomAccessRequest,
        reason: str,
    ) -> ClassroomAccessDecision:
        """Build a denied decision without echoing unapproved categories as approved."""
        return ClassroomAccessDecision(
            allowed=False,
            operation=request.operation,
            approved_data_categories=(),
            approved_oauth_scopes=(),
            reason=reason,
        )
