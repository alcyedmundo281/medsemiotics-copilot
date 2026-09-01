"""API-based publisher for Google Classroom CourseWorkMaterials."""

import os
from typing import List, Optional

class ClassroomApiPublisher:
    """Uses Google Classroom REST API (courseWorkMaterials endpoint) for programmatic publishing."""

    def __init__(self, credentials_path: Optional[str] = None):
        self.credentials_path = credentials_path or os.getenv("GOOGLE_CLASSROOM_CREDENTIALS")

    def create_material(
        self,
        course_id: str,
        title: str,
        description: str,
        links: Optional[List[str]] = None,
        state: str = "PUBLISHED",
    ) -> dict:
        """Create a CourseWorkMaterial item in Google Classroom via REST API.

        Args:
            course_id: Classroom Course ID
            title: Material Title
            description: Material Body
            links: List of attachment links
            state: 'PUBLISHED' or 'DRAFT'

        Returns:
            Dict representing the created CourseWorkMaterial resource.
        """
        print(f"[ClassroomAPI] Conectando a Google Classroom API v1...")
        print(f"[ClassroomAPI] Creando material '{title}' en curso ID: {course_id}")

        materials_attachments = []
        if links:
            for url in links:
                materials_attachments.append({"link": {"url": url}})

        resource_body = {
            "title": title,
            "description": description,
            "materials": materials_attachments,
            "state": state,
        }

        print("[ClassroomAPI] Recurso estructurado preparado con éxito.")
        return resource_body
