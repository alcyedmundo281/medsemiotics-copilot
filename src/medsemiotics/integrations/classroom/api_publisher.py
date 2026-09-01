"""Build Google Classroom courseWorkMaterials request bodies.

This module only assembles the request payload. It performs no network call and holds no
credential, so a caller must carry out the authenticated request itself under the project's
Classroom access policy.
"""

import os
from typing import Any


class ClassroomApiPublisher:
    """Assemble courseWorkMaterials request bodies for the Classroom REST API."""

    def __init__(self, credentials_path: str | None = None) -> None:
        """Record where a caller would find the Classroom credential, without reading it."""
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CLASSROOM_CREDENTIALS")

    def build_material_request(
        self,
        course_id: str,
        title: str,
        description: str,
        links: list[str] | None = None,
        state: str = "DRAFT",
    ) -> dict[str, Any]:
        """Build the request body for one courseWorkMaterial.

        Args:
            course_id: Classroom course identifier.
            title: Material title.
            description: Material body.
            links: URLs to attach as link materials.
            state: 'DRAFT' (default) or 'PUBLISHED'. Nothing is sent by this method.

        Returns:
            The request body a caller may POST to courses.courseWorkMaterials.create.
        """
        materials = [{"link": {"url": url}} for url in links or ()]
        return {
            "title": title,
            "description": description,
            "materials": materials,
            "state": state,
            "courseId": course_id,
        }
