"""Tests for GET /health endpoint."""

from fastapi.testclient import TestClient

from medsemiotics.api.app import app

client = TestClient(app)


def test_health_check_status_code() -> None:
    """Verify GET /health returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_payload() -> None:
    """Verify GET /health returns the exact expected payload."""
    response = client.get("/health")
    assert response.json() == {
        "status": "ok",
        "service": "medsemiotics-teaching-copilot",
    }
