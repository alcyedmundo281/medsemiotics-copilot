"""Unit tests for academic domain models (Course, SemesterConfig)."""

import pytest
from pydantic import ValidationError

from medsemiotics.domain.academic import Course, SemesterConfig


class TestCourseDomainModel:
    """Test suite for Course domain model validation and normalization."""

    def test_valid_course(self) -> None:
        """Verify standard valid course creation."""
        course = Course(code="NEURO", name="Neurología", active=True)
        assert course.code == "NEURO"
        assert course.name == "Neurología"
        assert course.active is True

    def test_course_default_active(self) -> None:
        """Verify active defaults to True."""
        course = Course(code="GASTRO", name="Gastroenterología")
        assert course.active is True

    def test_course_code_normalization_uppercase_and_trim(self) -> None:
        """Verify course code is normalized to uppercase and whitespace stripped."""
        course = Course(code="  neuro_101  ", name="Neurología Clínica")
        assert course.code == "NEURO_101"

    @pytest.mark.parametrize(
        "invalid_code",
        [
            "",
            "   ",
            "NEURO@MED",
            "NEURO 101",
            "GASTRO#1",
            "GASTRO.MED",
        ],
    )
    def test_invalid_course_codes(self, invalid_code: str) -> None:
        """Verify rejection of invalid course code patterns."""
        with pytest.raises(ValidationError):
            Course(code=invalid_code, name="Valid Course Name")

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "",
            "   ",
        ],
    )
    def test_invalid_course_name_empty(self, invalid_name: str) -> None:
        """Verify rejection of empty or whitespace-only course names."""
        with pytest.raises(ValidationError):
            Course(code="NEURO", name=invalid_name)

    def test_course_immutability(self) -> None:
        """Verify Course instance is frozen."""
        course = Course(code="NEURO", name="Neurología")
        with pytest.raises(ValidationError):
            course.active = False  # type: ignore[misc]


class TestSemesterConfigDomainModel:
    """Test suite for SemesterConfig domain model."""

    def test_valid_semester_config(self) -> None:
        """Verify creating a valid semester configuration."""
        config = SemesterConfig(
            semester_id="2026-2",
            display_name="2026-2",
            active=True,
            courses=[
                Course(code="NEURO", name="Neurología"),
                Course(code="GASTRO", name="Gastroenterología"),
            ],
        )
        assert config.semester_id == "2026-2"
        assert config.display_name == "2026-2"
        assert config.active is True
        assert len(config.courses) == 2

    @pytest.mark.parametrize(
        "valid_id",
        ["2026-1", "2026-2", "2027-1", "2030-2", " 2026-1 "],
    )
    def test_valid_semester_id_formats(self, valid_id: str) -> None:
        """Verify valid semester ID formats are accepted and trimmed."""
        config = SemesterConfig(
            semester_id=valid_id,
            display_name="Semester Display",
            active=True,
            courses=[Course(code="NEURO", name="Neurología")],
        )
        assert config.semester_id == valid_id.strip()

    @pytest.mark.parametrize(
        "invalid_id",
        [
            "",
            "   ",
            "2026",
            "2026-0",
            "2026-3",
            "2026-FALL",
            "26-1",
            "2026/1",
            "2026_1",
        ],
    )
    def test_invalid_semester_ids(self, invalid_id: str) -> None:
        """Verify rejection of invalid semester ID formats."""
        with pytest.raises(ValidationError):
            SemesterConfig(
                semester_id=invalid_id,
                display_name="Display Name",
                active=True,
                courses=[Course(code="NEURO", name="Neurología")],
            )

    def test_empty_courses_rejected(self) -> None:
        """Verify semester config must contain at least one course."""
        with pytest.raises(ValidationError, match="at least one course"):
            SemesterConfig(
                semester_id="2026-2",
                display_name="2026-2",
                active=True,
                courses=[],
            )

    def test_duplicate_course_codes_rejected(self) -> None:
        """Verify duplicate course codes within the same semester are rejected."""
        with pytest.raises(ValidationError, match="Duplicate course codes detected"):
            SemesterConfig(
                semester_id="2026-2",
                display_name="2026-2",
                active=True,
                courses=[
                    Course(code="NEURO", name="Neurología A"),
                    Course(code="neuro", name="Neurología B"),  # normalizes to NEURO
                ],
            )

    @pytest.mark.parametrize(
        "invalid_type_value",
        [123, ["not_a_str"], None, {"dict": "val"}],
    )
    def test_course_non_string_fields(self, invalid_type_value: object) -> None:
        """Verify passing non-string values to Course fields raises ValidationError."""
        with pytest.raises(ValidationError):
            Course(code=invalid_type_value, name="Valid Name")  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            Course(code="NEURO", name=invalid_type_value)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "invalid_type_value",
        [123, ["not_a_str"], None, {"dict": "val"}],
    )
    def test_semester_config_non_string_fields(self, invalid_type_value: object) -> None:
        """Verify passing non-string values to SemesterConfig fields raises ValidationError."""
        with pytest.raises(ValidationError):
            SemesterConfig(
                semester_id=invalid_type_value,  # type: ignore[arg-type]
                display_name="Display",
                active=True,
                courses=[Course(code="NEURO", name="Neurología")],
            )
        with pytest.raises(ValidationError):
            SemesterConfig(
                semester_id="2026-2",
                display_name=invalid_type_value,  # type: ignore[arg-type]
                active=True,
                courses=[Course(code="NEURO", name="Neurología")],
            )

    @pytest.mark.parametrize("blank_display", ["", "   "])
    def test_semester_config_blank_display_name(self, blank_display: str) -> None:
        """Verify blank display_name is rejected."""
        with pytest.raises(ValidationError):
            SemesterConfig(
                semester_id="2026-2",
                display_name=blank_display,
                active=True,
                courses=[Course(code="NEURO", name="Neurología")],
            )
