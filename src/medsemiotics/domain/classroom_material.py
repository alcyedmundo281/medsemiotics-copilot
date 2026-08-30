"""One faculty-reviewed, folder-backed material package for Google Classroom."""

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from medsemiotics.domain.academic import (
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)
from medsemiotics.domain.classroom_action import ClassroomActionType
from medsemiotics.domain.external_courses import normalize_course_name
from medsemiotics.domain.topics import validate_and_normalize_topic_id

MAX_CLASSROOM_MATERIALS = 20


class MaterialResourceType(StrEnum):
    """Faculty-facing classification for resources Classroom receives as HTTPS links."""

    URL = "url"
    PDF = "pdf"
    PPTX = "pptx"
    DOC = "doc"
    SHEET = "sheet"


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        msg = f"{field_name} must be a string"
        raise ValueError(msg)
    cleaned = value.strip()
    if not cleaned:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    return cleaned


def _https_url(value: object, field_name: str) -> str:
    cleaned = _required_text(value, field_name)
    parsed = urlsplit(cleaned)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        msg = f"{field_name} must be an absolute HTTPS URL without embedded credentials"
        raise ValueError(msg)
    return cleaned


def _digest(parts: list[object]) -> str:
    canonical = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ClassroomMaterialResource(BaseModel):
    """One reviewed resource linked from the material package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_type: MaterialResourceType
    title: Annotated[str, Field(max_length=300)]
    url: str

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return _required_text(value, "title")

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> str:
        return _https_url(value, "url")


class ClassroomMaterialPackagePlan(BaseModel):
    """Exactly one student-visible Classroom material, reviewed before publication."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_type: ClassroomActionType = ClassroomActionType.PUBLISH_COURSEWORK_MATERIAL
    semester_id: str
    course_code: str
    external_course_id: str
    topic_id: str
    title: Annotated[str, Field(max_length=3000)]
    description: Annotated[str | None, Field(max_length=30_000)] = None
    folder_url: str
    resources: Annotated[tuple[ClassroomMaterialResource, ...], Field(max_length=19)] = ()
    prepared_by: str
    prepared_at: datetime

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: ClassroomActionType) -> ClassroomActionType:
        if value is not ClassroomActionType.PUBLISH_COURSEWORK_MATERIAL:
            msg = "Material package plan can only describe publish_coursework_material"
            raise ValueError(msg)
        return value

    @field_validator("semester_id", mode="before")
    @classmethod
    def validate_semester_id(cls, value: object) -> str:
        return validate_and_normalize_semester_id(value)

    @field_validator("course_code", mode="before")
    @classmethod
    def validate_course_code(cls, value: object) -> str:
        return validate_and_normalize_course_code(value)

    @field_validator("topic_id", mode="before")
    @classmethod
    def validate_topic_id(cls, value: object) -> str:
        return validate_and_normalize_topic_id(value)

    @field_validator("external_course_id", "title", "prepared_by", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        return _required_text(value, getattr(info, "field_name", "field"))

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = _required_text(value, "description")
        return cleaned

    @field_validator("folder_url", mode="before")
    @classmethod
    def validate_folder_url(cls, value: object) -> str:
        return _https_url(value, "folder_url")

    @field_validator("prepared_at")
    @classmethod
    def validate_prepared_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            msg = "prepared_at must be timezone-aware"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_materials(self) -> "ClassroomMaterialPackagePlan":
        urls = [self.folder_url, *(resource.url for resource in self.resources)]
        if len(urls) > MAX_CLASSROOM_MATERIALS:
            msg = (
                f"A Classroom material package may contain at most {MAX_CLASSROOM_MATERIALS} links"
            )
            raise ValueError(msg)
        if len(urls) != len(set(urls)):
            msg = "Material package URLs must be unique, including the folder URL"
            raise ValueError(msg)
        if not normalize_course_name(self.title):
            msg = "title must contain at least one comparable character"
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def identity_key(self) -> str:
        """Stable identity preventing repeated publication of the same topic/title package."""
        return _digest(
            [
                str(self.action_type),
                self.semester_id,
                self.course_code,
                self.external_course_id,
                self.topic_id,
                normalize_course_name(self.title),
            ]
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_fingerprint(self) -> str:
        """Digest binding approval to the exact folder, description, and resource list."""
        return _digest(
            [
                self.identity_key,
                self.title,
                self.description or "",
                self.folder_url,
                [resource.model_dump(mode="json") for resource in self.resources],
            ]
        )
