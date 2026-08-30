"""Normalize Google Classroom discovery results into provider-neutral private snapshots."""

from medsemiotics.domain.classroom_discovery import (
    ClassroomCourseDiscovery,
    ClassroomCourseState,
)
from medsemiotics.domain.exceptions import ExternalCourseSnapshotError
from medsemiotics.domain.external_courses import (
    ExternalCourse,
    ExternalCourseLifecycle,
    ExternalCourseProvider,
    ExternalCourseSnapshot,
)

LIFECYCLE_BY_CLASSROOM_STATE: dict[ClassroomCourseState, ExternalCourseLifecycle] = {
    ClassroomCourseState.ACTIVE: ExternalCourseLifecycle.ACTIVE,
    ClassroomCourseState.ARCHIVED: ExternalCourseLifecycle.ARCHIVED,
    ClassroomCourseState.PROVISIONED: ExternalCourseLifecycle.PROVISIONED,
    ClassroomCourseState.DECLINED: ExternalCourseLifecycle.DECLINED,
    ClassroomCourseState.SUSPENDED: ExternalCourseLifecycle.SUSPENDED,
}


class ClassroomSnapshotNormalizer:
    """Convert one authorized Classroom read into a provider-neutral snapshot.

    The normalizer performs no I/O and holds no authorization of its own: it consumes a
    `ClassroomCourseDiscovery` that the Loop 0.6B read boundary already authorized and sanitized.
    """

    _PROVIDER = ExternalCourseProvider.GOOGLE_CLASSROOM

    def normalize(self, discovery: ClassroomCourseDiscovery) -> ExternalCourseSnapshot:
        """Map an authorized discovery result onto provider-neutral course models.

        Args:
            discovery: Sanitized result produced by the Classroom read boundary.

        Returns:
            Deterministic ExternalCourseSnapshot carrying the same provenance.

        Raises:
            ExternalCourseSnapshotError: If a course state has no provider-neutral equivalent or
                the resulting snapshot fails validation.
        """
        courses = [
            ExternalCourse(
                provider=self._PROVIDER,
                external_id=course.course_id,
                display_name=course.name,
                section=course.section,
                lifecycle=self._map_lifecycle(course.course_state),
                link=course.alternate_link,
            )
            for course in discovery.courses
        ]

        try:
            return ExternalCourseSnapshot(
                provider=self._PROVIDER,
                captured_at=discovery.retrieved_at,
                requested_by=discovery.requested_by,
                source_reference=discovery.source_deployment_id,
                approved_scopes=discovery.approved_oauth_scopes,
                courses=tuple(courses),
            )
        except ValueError as err:
            msg = f"Classroom discovery could not be normalized into a snapshot: {err}"
            raise ExternalCourseSnapshotError(msg) from err

    @staticmethod
    def _map_lifecycle(state: ClassroomCourseState) -> ExternalCourseLifecycle:
        """Translate a Classroom course state without inventing a default."""
        try:
            return LIFECYCLE_BY_CLASSROOM_STATE[state]
        except KeyError as err:
            msg = f"Classroom course state '{state.value}' has no provider-neutral equivalent"
            raise ExternalCourseSnapshotError(msg) from err
