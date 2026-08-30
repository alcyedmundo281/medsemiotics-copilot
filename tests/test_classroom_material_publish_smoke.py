"""Operator-contract checks for the Loop 0.7D material publication tool."""

import argparse
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "classroom_material_publish_smoke.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("classroom_material_publish_smoke", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resource_json_is_strict_and_supports_forms() -> None:
    module = load_script()

    resource = module._parse_resource(
        '{"resource_type":"form","title":"Chequeo formativo",'
        '"url":"https://docs.google.com/forms/d/example/viewform"}'
    )

    assert resource.resource_type.value == "form"
    assert resource.title == "Chequeo formativo"


@pytest.mark.parametrize(
    "value",
    [
        "not-json",
        '{"resource_type":"form","title":"X","url":"http://example.test"}',
        '{"resource_type":"form","title":"X","url":"https://example.test","extra":true}',
    ],
)
def test_resource_json_fails_closed(value: str) -> None:
    module = load_script()

    with pytest.raises(argparse.ArgumentTypeError):
        module._parse_resource(value)


def test_script_preserves_preflight_no_op_before_google_configuration() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    no_op = source.index("ClassroomActionStatus.ALREADY_APPLIED")
    deployment = source.index("deployment = load_apps_script_deployment()")
    publish = source.index("record = writer.publish(")
    ledger = source.index("ledger.append(record)")

    assert no_op < deployment < publish < ledger
    assert "GOOGLE_CLASSROOM_COURSEWORK_MATERIALS_SCOPE" in source
    assert "ClassroomDataCategory.OWN_COURSEWORK_MATERIAL" in source


def test_operator_output_is_safe_for_default_windows_consoles() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "✓" not in source
    assert "✗" not in source
