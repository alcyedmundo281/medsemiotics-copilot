"""Deterministic data-minimization and OAuth policy for Google Classroom access."""

from dataclasses import dataclass
from typing import ClassVar

from medsemiotics.domain.classroom_access import (
    GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,
    GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,
    GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,
    ClassroomAccessDecision,
    ClassroomAccessRequest,
    ClassroomDataCategory,
    ClassroomOperation,
)
from medsemiotics.domain.exceptions import ClassroomAccessPolicyError


@dataclass(frozen=True)
class _OperationAllowance:
    """The exact authority one declared operation may request, and nothing more."""

    categories: tuple[ClassroomDataCategory, ...]
    scopes: tuple[str, ...]
    external_mutation: bool
    mutation_denial: str
    category_denial: str
    scope_denial: str
    grant_reason: str


class ClassroomAccessPolicy:
    """Authorize only the narrow operations the public Classroom contract declares.

    Loop 0.6A permits metadata-only course discovery. Loop 0.6F adds exactly one write: creating a
    coursework draft in a course the dedicated account teaches. Every other operation, category,
    scope, and mutation flag fails closed.
    """

    _ALLOWANCES: ClassVar[dict[ClassroomOperation, _OperationAllowance]] = {
        ClassroomOperation.COURSE_DISCOVERY: _OperationAllowance(
            categories=(ClassroomDataCategory.COURSE_METADATA,),
            scopes=(GOOGLE_CLASSROOM_COURSES_READONLY_SCOPE,),
            external_mutation=False,
            mutation_denial="Course discovery is read-only and cannot mutate Classroom.",
            category_denial=(
                "Only course_metadata is permitted; rosters, student identifiers, coursework, "
                "submissions, and grades are prohibited."
            ),
            scope_denial=(
                "Course discovery requires exactly the classroom.courses.readonly OAuth scope."
            ),
            grant_reason="Minimal read-only course discovery is permitted.",
        ),
        ClassroomOperation.COURSEWORK_DRAFT_CREATE: _OperationAllowance(
            categories=(ClassroomDataCategory.OWN_COURSEWORK_DRAFT,),
            scopes=(GOOGLE_CLASSROOM_COURSEWORK_WRITE_SCOPE,),
            external_mutation=True,
            mutation_denial=(
                "Creating a coursework draft mutates Classroom and must be declared as a mutation."
            ),
            category_denial=(
                "Only own_coursework_draft is permitted; rosters, student identifiers, existing "
                "coursework, submissions, and grades are prohibited."
            ),
            scope_denial=(
                "Creating a coursework draft requires exactly the "
                "classroom.coursework.students OAuth scope."
            ),
            grant_reason=(
                "Creating one coursework draft is permitted; grades are never read or written."
            ),
        ),
        ClassroomOperation.COURSEWORK_MATERIAL_PUBLISH: _OperationAllowance(
            categories=(ClassroomDataCategory.OWN_COURSEWORK_MATERIAL,),
            scopes=(GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE,),
            external_mutation=True,
            mutation_denial=(
                "Publishing course material mutates Classroom and must be declared as a mutation."
            ),
            category_denial=(
                "Only own_coursework_material is permitted; rosters, student identifiers, "
                "submissions, grades, and existing coursework are prohibited."
            ),
            scope_denial=(
                "Publishing course material requires exactly the "
                "classroom.courseworkmaterials OAuth scope."
            ),
            grant_reason=(
                "Publishing one approved course material package is permitted; no student or "
                "grading data is read or written."
            ),
        ),
    }

    def evaluate(self, request: ClassroomAccessRequest) -> ClassroomAccessDecision:
        """Evaluate one request without calling Google or mutating any external state.

        Args:
            request: The declared operation, categories, scopes, and mutation flag.

        Returns:
            An explainable allow or deny decision.

        Raises:
            ClassroomAccessPolicyError: If the request declares an operation the contract does
                not define, which cannot be evaluated at all.
        """
        allowance = self._ALLOWANCES.get(request.operation)
        if allowance is None:
            msg = (
                f"Operation '{request.operation}' is not part of the Classroom contract "
                "and cannot be evaluated."
            )
            raise ClassroomAccessPolicyError(msg)
        if request.external_mutation != allowance.external_mutation:
            return self._deny(request, allowance.mutation_denial)
        if request.data_categories != allowance.categories:
            return self._deny(request, allowance.category_denial)
        if request.oauth_scopes != allowance.scopes:
            return self._deny(request, allowance.scope_denial)
        return ClassroomAccessDecision(
            allowed=True,
            operation=request.operation,
            approved_data_categories=allowance.categories,
            approved_oauth_scopes=allowance.scopes,
            reason=allowance.grant_reason,
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
