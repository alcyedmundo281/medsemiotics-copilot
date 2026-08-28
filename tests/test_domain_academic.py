"""Unit tests for academic domain models (Course, SemesterConfig, validation rules)."""

import pytest
from pydantic import ValidationError

from medsemiotics.domain.academic import (
    Course,
    SemesterConfig,
    validate_and_normalize_course_code,
    validate_and_normalize_semester_id,
)


class TestValidationHelpers:
    """Test suite for helper validation functions."""

    def test_validate_and_normalize_course_code_valid(self) -> None:
        """Verify normalization of valid course codes."""
        assert validate_and_normalize_course_code("neuro") == "NEURO"
        assert validate_and_normalize_course_code("  gastro  ") == "GASTRO"
        assert validate_and_normalize_course_code("NEURO_CLIN-1") == "NEURO_CLIN-1"

    @pytest.mark.parametrize(
        "invalid_code",
        ["", "   ", "NEURO@CLIN", "NEURO CLIN", "NEURO.CLIN", 123, None],
    )
    def test_validate_and_normalize_course_code_invalid(self, invalid_code: object) -> None:
        """Verify invalid course codes raise ValueError."""
        with pytest.raises(ValueError):
            validate_and_normalize_course_code(invalid_code)

    def test_validate_and_normalize_semester_id_valid(self) -> None:
        """Verify normalization of valid semester IDs."""
        assert validate_and_normalize_semester_id("2026-1") == "2026-1"
        assert validate_and_normalize_semester_id(" 2026-2 ") == "2026-2"

    @pytest.mark.parametrize(
        "invalid_semester",
        ["", "2026", "2026-0", "2026-3", "2026-SPRING", 20261, None],
    )
    def test_validate_and_normalize_semester_id_invalid(self, invalid_semester: object) -> None:
        """Verify invalid semester IDs raise ValueError."""
        with pytest.raises(ValueError):
            validate_and_normalize_semester_id(invalid_semester)


class TestCourseDomainModel:
    """Test suite for Course domain model."""

    def test_valid_course_creation(self) -> None:
        """Verify creating a valid course model."""
        course = Course(code="neuro", name="  Neurología Clínica  ", active=True)
        assert course.code == "NEURO"
        assert course.name == "Neurología Clínica"
        assert course.active is True

    def test_course_default_active_is_true(self) -> None:
        """Verify default active status is True."""
        course = Course(code="GASTRO", name="Gastroenterología")
        assert course.active is True

    def test_course_is_immutable(self) -> None:
        """Verify Course instance is frozen/immutable."""
        course = Course(code="NEURO", name="Neurología")
        with pytest.raises(ValidationError):
            course.active = False  # type: ignore[misc]


class TestSemesterConfigDomainModel:
    """Test suite for SemesterConfig domain model."""

    def test_valid_semester_config(self) -> None:
        """Verify creating a valid semester configuration with explicit timezone."""
        config = SemesterConfig(
            semester_id="2026-2",
            display_name="2026-2",
            active=True,
            timezone="America/Guayaquil",
            courses=[
                Course(code="NEURO", name="Neurología"),
                Course(code="GASTRO", name="Gastroenterología"),
            ],
        )
        assert config.semester_id == "2026-2"
        assert config.display_name == "2026-2"
        assert config.active is True
        assert config.timezone == "America/Guayaquil"
        assert config.tz.key == "America/Guayaquil"
        assert len(config.courses) == 2

    def test_missing_timezone_rejected(self) -> None:
        """Verify missing timezone field in SemesterConfig raises ValidationError."""
        with pytest.raises(ValidationError, match="Field required"):
            SemesterConfig(
                semester_id="2026-2",
                display_name="2026-2",
                active=True,
                courses=[Course(code="NEURO", name="Neurología")],
            )  # type: ignore[call-arg]

    def test_invalid_timezone_rejected(self) -> None:
        """Verify unknown or invalid IANA timezone string raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid or unknown IANA timezone"):
            SemesterConfig(
                semester_id="2026-2",
                display_name="2026-2",
                active=True,
                timezone="Invalid/NonExistent_TZ",
                courses=[Course(code="NEURO", name="Neurología")],
            )

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
            timezone="America/Guayaquil",
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
                timezone="America/Guayaquil",
                courses=[Course(code="NEURO", name="Neurología")],
            )

    def test_empty_courses_rejected(self) -> None:
        """Verify semester config must contain at least one course."""
        with pytest.raises(ValidationError, match="at least one course"):
            SemesterConfig(
                semester_id="2026-2",
                display_name="2026-2",
                active=True,
                timezone="America/Guayaquil",
                courses=[],
            )

    def test_duplicate_course_codes_rejected(self) -> None:
        """Verify duplicate course codes within the same semester are rejected."""
        with pytest.raises(ValidationError, match="Duplicate course codes detected"):
            SemesterConfig(
                semester_id="2026-2",
                display_name="2026-2",
                active=True,
                timezone="America/Guayaquil",
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
                timezone="America/Guayaquil",
                courses=[Course(code="NEURO", name="Neurología")],
            )
        with pytest.raises(ValidationError):
            SemesterConfig(
                semester_id="2026-2",
                display_name=invalid_type_value,  # type: ignore[arg-type]
                active=True,
                timezone="America/Guayaquil",
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
                timezone="America/Guayaquil",
                courses=[Course(code="NEURO", name="Neurología")],
            )
