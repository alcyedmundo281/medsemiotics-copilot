"""Build one reviewable Classroom draft plan from a faculty assignment catalog."""

from medsemiotics.domain.assignment_catalog import (
    AssignmentRubric,
    AssignmentTemplate,
    CatalogAssignmentDraft,
    CatalogAssignmentDraftRequest,
)
from medsemiotics.domain.coordination_view import CourseCoordinationEntry
from medsemiotics.domain.exceptions import CatalogClassroomDraftError
from medsemiotics.services.assignment_catalog_repository import AssignmentCatalogRepository
from medsemiotics.services.classroom_action_plan import ClassroomActionPlanner
from medsemiotics.services.syllabus_repository import SyllabusRepository


class CatalogClassroomAssignmentService:
    """Join catalog, syllabus, and coordination state without executing Classroom writes."""

    def __init__(
        self,
        *,
        assignment_repository: AssignmentCatalogRepository,
        syllabus_repository: SyllabusRepository,
        action_planner: ClassroomActionPlanner,
    ) -> None:
        self._assignment_repository = assignment_repository
        self._syllabus_repository = syllabus_repository
        self._action_planner = action_planner

    def prepare_draft(
        self,
        *,
        request: CatalogAssignmentDraftRequest,
        entry: CourseCoordinationEntry,
    ) -> CatalogAssignmentDraft:
        """Prepare one catalog-backed plan that remains separate from approval and execution."""
        if request.course_code != entry.course_code:
            msg = (
                f"Draft request course '{request.course_code}' does not match coordination "
                f"entry '{entry.course_code}'."
            )
            raise CatalogClassroomDraftError(msg)

        assignment = self._assignment_repository.get_assignment(
            request.semester_id,
            request.course_code,
            request.assignment_id,
        )
        rubric = self._assignment_repository.get_rubric(
            request.semester_id,
            request.course_code,
            assignment.rubric_id,
        )
        syllabus = self._syllabus_repository.get(request.semester_id, request.course_code)
        syllabus_topic_ids = {topic.topic_id for topic in syllabus.topics}
        if assignment.topic_id not in syllabus_topic_ids:
            msg = (
                f"Assignment '{assignment.assignment_id}' references topic "
                f"'{assignment.topic_id}', which is absent from the tracked syllabus."
            )
            raise CatalogClassroomDraftError(msg)

        plan = self._action_planner.plan_coursework_draft(
            entry=entry,
            semester_id=request.semester_id,
            topic_id=assignment.topic_id,
            title=assignment.title,
            prepared_by=request.prepared_by,
            instructions=self._render_instructions(assignment, rubric),
            due_date=request.due_date,
        )
        return CatalogAssignmentDraft(assignment=assignment, rubric=rubric, plan=plan)

    @staticmethod
    def _render_instructions(
        assignment: AssignmentTemplate,
        rubric: AssignmentRubric,
    ) -> str:
        deliverables = "\n".join(f"- {item}" for item in assignment.deliverables)
        criteria = "\n".join(
            f"- {item.title} ({item.weight_percent}%): {item.description}"
            for item in rubric.criteria
        )
        levels = "\n".join(f"- {item.label}: {item.description}" for item in rubric.levels)
        return (
            f"{assignment.prompt}\n\n"
            f"Productos esperados:\n{deliverables}\n\n"
            f"Rúbrica cualitativa para revisión docente — {rubric.title}:\n{criteria}\n\n"
            f"Escala cualitativa:\n{levels}\n\n"
            "Privacidad: use exclusivamente casos sintéticos o desidentificados. No incluya "
            "nombres, correos, identificadores de estudiantes ni datos identificables de pacientes."
        )
