"""Trivial import test to verify package resolution."""

import medsemiotics


def test_package_import() -> None:
    """Verify medsemiotics package can be imported and has version defined."""
    assert medsemiotics.__version__ == "0.1.0"
