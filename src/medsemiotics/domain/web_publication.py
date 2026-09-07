"""Domain models for PowerSemiotics web module publication.

Encapsulates course web mappings, module publication specifications,
card layouts, and execution results according to the project's
KNOW -> REASON -> ACT boundary.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CourseWebSection(BaseModel):
    """Configuration mapping an academic course to its PowerSemiotics web hub."""

    model_config = ConfigDict(frozen=True)

    course_code: str = Field(description="Internal course identifier (e.g. GASTRO, NEURO)")
    section_slug: str = Field(description="Web folder slug (e.g. gastroenterologia, neurologia)")
    hub_filename: str = Field(description="Hub HTML filename (e.g. gastroenterologia.html)")
    display_name: str = Field(description="Display name of the course")

    # Canonical mapping for active MedSemiotics courses
    KNOWN_SECTIONS: ClassVar[dict[str, tuple[str, str, str]]] = {
        "GASTRO": ("gastroenterologia", "gastroenterologia.html", "Gastroenterología"),
        "GASTROENTEROLOGIA": ("gastroenterologia", "gastroenterologia.html", "Gastroenterología"),
        "GASTROENTEROLOGÍA": ("gastroenterologia", "gastroenterologia.html", "Gastroenterología"),
        "NEURO": ("neurologia", "neurologia.html", "Neurología"),
        "NEUROLOGIA": ("neurologia", "neurologia.html", "Neurología"),
        "NEUROLOGÍA": ("neurologia", "neurologia.html", "Neurología"),
    }

    @classmethod
    def from_course(cls, course_identifier: str) -> CourseWebSection:
        """Resolve a CourseWebSection from a code, folder name, or human title."""
        key = course_identifier.strip().upper()
        if key in cls.KNOWN_SECTIONS:
            section_slug, hub_file, display_name = cls.KNOWN_SECTIONS[key]
            return cls(
                course_code=key if len(key) <= 6 else ("GASTRO" if "GASTRO" in key else "NEURO"),
                section_slug=section_slug,
                hub_filename=hub_file,
                display_name=display_name,
            )
        # Fallback: normalize lowercase slug
        slug = course_identifier.strip().lower().replace("_", "-")
        hub = f"{slug}.html"
        return cls(
            course_code=slug.upper(),
            section_slug=slug,
            hub_filename=hub,
            display_name=course_identifier.strip(),
        )


class WebModuleSpec(BaseModel):
    """Specification of a web module to be published into the medsemiotics portal."""

    model_config = ConfigDict(frozen=True)

    course: str = Field(description="Course code or name (e.g. GASTRO, NEURO)")
    slug: str = Field(description="Module URL slug (e.g. enfermedad-crohn)")
    title: str = Field(description="Display title for the module and its hub card")
    description: str = Field(description="Summary paragraph displayed on the hub card")
    source_html_path: Path = Field(description="Path to local source HTML file")
    icon: str = Field(
        default="notes-medical",
        description="Font Awesome icon name (without 'fa-' or 'fas fa-')",
    )
    canonical_base_url: str = Field(
        default="https://powersemiotics.com/medsemiotics",
        description="Base URL for canonical links",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        """Ensure slug is clean, lowercased, and without .html extension."""
        cleaned = value.strip().lower()
        if cleaned.endswith(".html"):
            cleaned = cleaned[:-5]
        if not cleaned:
            msg = "Module slug must not be empty"
            raise ValueError(msg)
        return cleaned

    @field_validator("icon")
    @classmethod
    def validate_icon(cls, value: str) -> str:
        """Strip 'fa-' or 'fas fa-' prefixes if provided."""
        cleaned = value.strip().lower()
        for prefix in ("fas fa-", "far fa-", "fa-"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :]
        return cleaned or "notes-medical"

    def get_canonical_url(self, section_slug: str) -> str:
        """Build canonical URL for this module."""
        base = self.canonical_base_url.rstrip("/")
        return f"{base}/{section_slug}/{self.slug}.html"

    def get_relative_href(self, section_slug: str) -> str:
        """Build relative href from the course hub to this module."""
        return f"{section_slug}/{self.slug}.html"


class WebPublishPlan(BaseModel):
    """A deterministic, reviewable plan for publishing a module and updating the hub."""

    model_config = ConfigDict(frozen=True)

    spec: WebModuleSpec
    section: CourseWebSection
    target_module_path: Path
    target_hub_path: Path
    card_html: str
    card_already_exists: bool
    canonical_url: str
    relative_href: str


class WebPublishResult(BaseModel):
    """Outcome of a web publication operation."""

    model_config = ConfigDict(frozen=True)

    module_copied: bool
    hub_updated: bool
    sitemap_updated: bool
    git_committed: bool
    git_pushed: bool
    published_url: str
    summary: str
