"""Plan a Google Classroom material post for local, human-driven browser publishing.

Nothing here contacts Google. The planner renders exactly what a human would paste into
Classroom, so the teacher reviews the post before it exists. Publishing stays a human action,
which is the same boundary the rest of the project applies to Calendar.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClassroomMaterialPlan:
    """A reviewable draft of one Classroom material post."""

    course_name: str
    title: str
    description: str
    topic_name: str | None = None
    links: tuple[str, ...] = field(default_factory=tuple)
    file_paths: tuple[str, ...] = field(default_factory=tuple)
    published: bool = False

    def render(self) -> str:
        """Render the plan as the text a human reviews before posting it."""
        lines = [
            f"Curso      : {self.course_name}",
            f"Sección    : {self.topic_name or '(sin sección)'}",
            f"Título     : {self.title}",
            "Descripción:",
            self.description,
        ]
        if self.links:
            lines.append("Enlaces adjuntos:")
            lines.extend(f"  - {link}" for link in self.links)
        if self.file_paths:
            lines.append("Archivos adjuntos:")
            lines.extend(f"  - {path}" for path in self.file_paths)
        lines.append("Estado     : BORRADOR — requiere publicación manual en Classroom.")
        return "\n".join(lines)


class ClassroomBrowserPublisher:
    """Build reviewable Classroom material drafts for local publishing."""

    def __init__(self, headless: bool = False, user_data_dir: str | None = None) -> None:
        """Record the browser preferences a future local automation would use."""
        self.headless = headless
        self.user_data_dir = user_data_dir

    def plan_material(
        self,
        course_name: str,
        title: str,
        description: str,
        topic_name: str | None = None,
        links: list[str] | None = None,
        file_paths: list[str] | None = None,
    ) -> ClassroomMaterialPlan:
        """Build the draft post for one course without contacting Google Classroom.

        Args:
            course_name: Name of the course, e.g. 'Neurología'.
            title: Material title.
            description: Body of the material.
            topic_name: Classroom topic under Trabajo de clase.
            links: Web URLs to attach.
            file_paths: Local files to attach.

        Returns:
            A reviewable plan. It is never published by this call.
        """
        return ClassroomMaterialPlan(
            course_name=course_name,
            title=title,
            description=description,
            topic_name=topic_name,
            links=tuple(links or ()),
            file_paths=tuple(file_paths or ()),
        )
