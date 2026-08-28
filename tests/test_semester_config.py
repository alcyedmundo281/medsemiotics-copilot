"""Unit tests for semester configuration and pointer file loaders."""

from pathlib import Path

import pytest

from medsemiotics.domain.exceptions import (
    SemesterConfigNotFoundError,
    SemesterConfigValidationError,
)
from medsemiotics.services.semester_config import (
    load_current_semester_id,
    load_semester_config,
)


class TestLoadSemesterConfig:
    """Test suite for load_semester_config service function."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        """Verify loading a valid semester YAML configuration."""
        yaml_file = tmp_path / "2026-1.yaml"
        yaml_file.write_text(
            """
semester_id: "2026-1"
display_name: "2026-1 (Primavera)"
active: true
courses:
  - code: "NEURO"
    name: "Neurología Clínica"
    active: true
  - code: "GASTRO"
    name: "Gastroenterología"
    active: false
""",
            encoding="utf-8",
        )

        config = load_semester_config(yaml_file)
        assert config.semester_id == "2026-1"
        assert config.display_name == "2026-1 (Primavera)"
        assert config.active is True
        assert len(config.courses) == 2
        assert config.courses[0].code == "NEURO"
        assert config.courses[1].code == "GASTRO"

    def test_load_utf8_special_characters(self, tmp_path: Path) -> None:
        """Verify UTF-8 encoding support for accents and medical terminology."""
        yaml_file = tmp_path / "2026-2.yaml"
        yaml_file.write_text(
            """
semester_id: "2026-2"
display_name: "Año Académico 2026 — Otoño"
active: true
courses:
  - code: "NEURO_CLIN"
    name: "Semiología Neurológica & Neuroanatomía Clínica"
    active: true
""",
            encoding="utf-8",
        )

        config = load_semester_config(yaml_file)
        assert config.courses[0].name == "Semiología Neurológica & Neuroanatomía Clínica"

    def test_load_explicit_timezone(self, tmp_path: Path) -> None:
        """Verify custom valid timezone is loaded and resolved."""
        yaml_file = tmp_path / "2026-2.yaml"
        yaml_file.write_text(
            """
semester_id: "2026-2"
display_name: "2026-2"
active: true
timezone: "America/Guayaquil"
courses:
  - code: "NEURO"
    name: "Neurología"
""",
            encoding="utf-8",
        )
        config = load_semester_config(yaml_file)
        assert config.timezone == "America/Guayaquil"
        assert config.tz.key == "America/Guayaquil"

    def test_invalid_timezone_rejected(self, tmp_path: Path) -> None:
        """Verify invalid or unrecognized timezone identifier is rejected."""
        yaml_file = tmp_path / "2026-2.yaml"
        yaml_file.write_text(
            """
semester_id: "2026-2"
display_name: "2026-2"
active: true
timezone: "Invalid/Timezone_XYZ"
courses:
  - code: "NEURO"
    name: "Neurología"
""",
            encoding="utf-8",
        )
        with pytest.raises(SemesterConfigValidationError, match="Invalid or unknown IANA timezone"):
            load_semester_config(yaml_file)

    def test_missing_file_raises_not_found(self, tmp_path: Path) -> None:
        """Verify missing semester file raises SemesterConfigNotFoundError."""
        missing_file = tmp_path / "non_existent.yaml"
        with pytest.raises(SemesterConfigNotFoundError, match="file not found"):
            load_semester_config(missing_file)

    def test_malformed_yaml_syntax_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify unparseable YAML syntax raises SemesterConfigValidationError."""
        bad_yaml = tmp_path / "bad_syntax.yaml"
        bad_yaml.write_text("semester_id: [unclosed list", encoding="utf-8")
        with pytest.raises(SemesterConfigValidationError, match="Malformed YAML"):
            load_semester_config(bad_yaml)

    def test_non_dict_root_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify YAML list or scalar root raises SemesterConfigValidationError."""
        list_yaml = tmp_path / "list_root.yaml"
        list_yaml.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(SemesterConfigValidationError, match="Expected a YAML mapping"):
            load_semester_config(list_yaml)

    def test_structurally_invalid_schema_raises_validation_error(self, tmp_path: Path) -> None:
        """Verify YAML missing required schema fields raises SemesterConfigValidationError."""
        invalid_yaml = tmp_path / "invalid_schema.yaml"
        invalid_yaml.write_text(
            """
display_name: "Missing semester_id"
active: true
courses: []
""",
            encoding="utf-8",
        )
        with pytest.raises(SemesterConfigValidationError, match="Validation failed"):
            load_semester_config(invalid_yaml)


class TestLoadCurrentSemesterId:
    """Test suite for load_current_semester_id pointer loader."""

    def test_load_valid_current_pointer(self, tmp_path: Path) -> None:
        """Verify reading a valid current_semester.yaml pointer."""
        pointer_file = tmp_path / "current_semester.yaml"
        pointer_file.write_text('semester_id: "2026-2"\n', encoding="utf-8")

        current_id = load_current_semester_id(pointer_file)
        assert current_id == "2026-2"

    def test_missing_pointer_raises_not_found(self, tmp_path: Path) -> None:
        """Verify missing current_semester.yaml raises SemesterConfigNotFoundError."""
        missing_pointer = tmp_path / "current_semester.yaml"
        with pytest.raises(SemesterConfigNotFoundError, match="pointer file not found"):
            load_current_semester_id(missing_pointer)

    @pytest.mark.parametrize(
        "invalid_content",
        [
            "semester_id: 2026-3\n",
            "semester_id: invalid\n",
            "display_name: 2026-2\n",
            "semester_id: 12345\n",
            "- item1\n- item2\n",
            "semester_id: [nested]\n",
        ],
    )
    def test_invalid_pointer_raises_validation_error(
        self, tmp_path: Path, invalid_content: str
    ) -> None:
        """Verify invalid pointer formats raise SemesterConfigValidationError."""
        bad_pointer = tmp_path / "current_semester.yaml"
        bad_pointer.write_text(invalid_content, encoding="utf-8")
        with pytest.raises(SemesterConfigValidationError):
            load_current_semester_id(bad_pointer)

    def test_load_semester_config_oserror(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Verify OS read failures raise SemesterConfigError."""
        from medsemiotics.domain.exceptions import SemesterConfigError

        sample_file = tmp_path / "test.yaml"
        sample_file.write_text("dummy", encoding="utf-8")

        def mock_read_text(*_args: object, **_kwargs: object) -> str:
            raise OSError("Disk failure")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        with pytest.raises(SemesterConfigError, match="Failed to read"):
            load_semester_config(sample_file)

    def test_load_current_semester_pointer_oserror(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify OS read failures for pointer raise SemesterConfigError."""
        from medsemiotics.domain.exceptions import SemesterConfigError

        pointer_file = tmp_path / "current_semester.yaml"
        pointer_file.write_text("dummy", encoding="utf-8")

        def mock_read_text(*_args: object, **_kwargs: object) -> str:
            raise OSError("Disk failure")

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        with pytest.raises(SemesterConfigError, match="Failed to read"):
            load_current_semester_id(pointer_file)
