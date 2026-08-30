"""Tests for the Loop 0.8A read-only backend contracts."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from medsemiotics.api import app as api_module
from medsemiotics.api.settings import (
    API_TOKEN_SECRET,
    CONFIG_ROOT_ENV_VAR,
    BackendSettings,
    load_backend_settings,
)

TOKEN = "backend-token-for-the-mobile-surface"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
CONFIG_ROOT = Path("config")


def configure(config_root: Path = CONFIG_ROOT, token: str | None = TOKEN) -> TestClient:
    """Bind the application to one configuration root and token."""
    api_module.configure(BackendSettings(config_root=config_root, api_token=token))
    return TestClient(api_module.app)


@pytest.fixture(autouse=True)
def reset_application_state() -> Iterator[None]:
    """Keep application state from leaking between tests."""
    yield
    for attribute in ("settings", "api_token", "services"):
        if hasattr(api_module.app.state, attribute):
            delattr(api_module.app.state, attribute)


class TestBackendSettings:
    """Verify the backend reads its own configuration, not a Google credential."""

    def test_reads_the_configuration_root_and_token(self) -> None:
        settings = load_backend_settings(
            {CONFIG_ROOT_ENV_VAR: "/srv/config", API_TOKEN_SECRET: f"  {TOKEN}  "}
        )

        assert settings.config_root == Path("/srv/config")
        assert settings.api_token == TOKEN
        assert settings.current_semester_pointer == Path("/srv/config/current_semester.yaml")

    def test_defaults_the_configuration_root(self) -> None:
        settings = load_backend_settings({})

        assert settings.config_root == CONFIG_ROOT
        assert settings.api_token is None


class TestLazyConfiguration:
    """Verify a server started without explicit wiring configures itself from the environment."""

    def test_configures_itself_on_first_use(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(CONFIG_ROOT_ENV_VAR, str(CONFIG_ROOT))
        monkeypatch.setenv(API_TOKEN_SECRET, TOKEN)
        for attribute in ("settings", "api_token", "services"):
            if hasattr(api_module.app.state, attribute):
                delattr(api_module.app.state, attribute)

        services = api_module.get_services()

        assert services.settings.config_root == CONFIG_ROOT
        assert services.current_semester_id() == "2026-2"


class TestAccessControl:
    """Verify academic state is never served to an unauthenticated caller."""

    def test_health_needs_no_token(self) -> None:
        response = configure(token=None).get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_rejects_a_request_without_a_token(self) -> None:
        response = configure().get("/v1/semester")

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    @pytest.mark.parametrize(
        "header",
        [
            {"Authorization": "Bearer wrong-token"},
            {"Authorization": TOKEN},
            {"Authorization": "Basic dXNlcjpwYXNz"},
            {"Authorization": "Bearer    "},
        ],
    )
    def test_rejects_a_malformed_or_wrong_token(self, header: dict[str, str]) -> None:
        response = configure().get("/v1/semester", headers=header)

        assert response.status_code == 401

    def test_refuses_to_serve_state_without_a_configured_token(self) -> None:
        response = configure(token=None).get("/v1/semester", headers=AUTH)

        assert response.status_code == 503
        assert API_TOKEN_SECRET in response.json()["detail"]


class TestSemesterEndpoint:
    """Verify the semester contract a mobile surface opens first."""

    def test_returns_the_active_semester_and_courses(self) -> None:
        response = configure().get("/v1/semester", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["semester_id"] == "2026-2"
        assert payload["timezone"] == "America/Guayaquil"
        assert [course["code"] for course in payload["courses"]] == ["GASTRO", "NEURO"]

    def test_reports_missing_configuration_without_a_filesystem_path(
        self,
        tmp_path: Path,
    ) -> None:
        response = configure(config_root=tmp_path).get("/v1/semester", headers=AUTH)

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert str(tmp_path) not in detail
        assert ".yaml" not in detail


class TestCourseStateEndpoint:
    """Verify what has been taught, and what comes next, without student data."""

    def test_returns_tracked_progress(self) -> None:
        response = configure().get("/v1/courses/neuro/state", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["course_code"] == "NEURO"
        assert payload["total_topics"] == 5
        assert payload["not_started_topics"] == 5
        assert payload["next_required_topic_id"] == "neuro-intro"
        assert [topic["topic_id"] for topic in payload["topics"]][:2] == [
            "neuro-intro",
            "mental-status",
        ]

    def test_reports_an_unknown_course_without_a_filesystem_path(self) -> None:
        response = configure().get("/v1/courses/CARDIO/state", headers=AUTH)

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "CARDIO" in detail
        assert "/" not in detail


class TestNextTopicEndpoint:
    """Verify the endpoint a phone opens before class."""

    def test_returns_the_next_topic_with_its_curated_guide(self) -> None:
        response = configure().get("/v1/courses/NEURO/next-topic", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["topic_id"] == "neuro-intro"
        assert payload["guide"]["topic_title"] == "Introducción a la semiología neurológica"
        assert len(payload["guide"]["learning_objectives"]) == 2
        assert payload["guide"]["common_pitfalls"]
        assert "not_started" in payload["note"]

    def test_reports_an_unknown_course(self) -> None:
        response = configure().get("/v1/courses/CARDIO/next-topic", headers=AUTH)

        assert response.status_code == 404
        assert "CARDIO" in response.json()["detail"]

    def test_reports_a_course_whose_required_topics_are_covered(self, tmp_path: Path) -> None:
        _write_minimal_config(tmp_path, required=False)

        response = configure(config_root=tmp_path).get("/v1/courses/NEURO/next-topic", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["topic_id"] is None
        assert payload["guide"] is None
        assert "already covered" in payload["note"]

    def test_reports_a_topic_without_a_curated_guide(self, tmp_path: Path) -> None:
        _write_minimal_config(tmp_path, required=True)

        response = configure(config_root=tmp_path).get("/v1/courses/NEURO/next-topic", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["topic_id"] == "neuro-intro"
        assert payload["guide"] is None
        assert "no guide" in payload["note"]


class TestGuideEndpoint:
    """Verify curated guidance is served exactly as the catalog publishes it."""

    def test_returns_one_curated_guide(self) -> None:
        response = configure().get("/v1/courses/NEURO/guides/cranial-nerves", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["topic_title"] == "Exploración de pares craneales"
        assert payload["teaching_questions"]
        assert payload["material_notes"]

    def test_reports_an_unknown_topic(self) -> None:
        response = configure().get("/v1/courses/NEURO/guides/unknown-topic", headers=AUTH)

        assert response.status_code == 404
        assert "unknown-topic" in response.json()["detail"]


def _write_minimal_config(root: Path, *, required: bool, inactive_course: bool = False) -> None:
    """Write a minimal tracked configuration with one NEURO topic and no guide catalog."""
    (root / "semesters").mkdir(parents=True, exist_ok=True)
    (root / "syllabi" / "2026-2").mkdir(parents=True, exist_ok=True)
    (root / "teaching_logs" / "2026-2").mkdir(parents=True, exist_ok=True)

    (root / "current_semester.yaml").write_text('semester_id: "2026-2"\n', encoding="utf-8")
    (root / "semesters" / "2026-2.yaml").write_text(
        'semester_id: "2026-2"\n'
        'display_name: "2026-2"\n'
        "active: true\n"
        'timezone: "America/Guayaquil"\n'
        "courses:\n"
        '  - code: "NEURO"\n'
        '    name: "Neurología"\n'
        "    active: true\n"
        + (
            '  - code: "GASTRO"\n    name: "Gastroenterología"\n    active: false\n'
            if inactive_course
            else ""
        ),
        encoding="utf-8",
    )
    (root / "syllabi" / "2026-2" / "NEURO.yaml").write_text(
        'semester_id: "2026-2"\n'
        'course_code: "NEURO"\n'
        "topics:\n"
        '  - topic_id: "neuro-intro"\n'
        "    planned_order: 1\n"
        "    planned_week: 1\n"
        f"    required: {'true' if required else 'false'}\n",
        encoding="utf-8",
    )
    (root / "teaching_logs" / "2026-2" / "NEURO.yaml").write_text(
        'semester_id: "2026-2"\ncourse_code: "NEURO"\nsessions: []\n',
        encoding="utf-8",
    )


class TestCoordinationEndpoint:
    """Verify the view a teacher checks when something is not wired."""

    def test_reports_every_active_course(self) -> None:
        response = configure().get("/v1/coordination", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["semester_id"] == "2026-2"
        assert [course["course_code"] for course in payload["courses"]] == ["GASTRO", "NEURO"]

    def test_declares_that_classroom_was_not_read(self) -> None:
        payload = configure().get("/v1/coordination", headers=AUTH).json()

        for course in payload["courses"]:
            assert course["classroom"]["status"] == "not_read"
            assert course["classroom"]["external_id"] is None
            assert any(blocker.startswith("classroom:") for blocker in course["blockers"])
        assert "no Google credential" in payload["note"]

    def test_carries_the_tracked_calendar_binding(self) -> None:
        payload = configure().get("/v1/coordination", headers=AUTH).json()
        neuro = next(course for course in payload["courses"] if course["course_code"] == "NEURO")

        assert neuro["calendar"]["status"] in {"configured", "disabled", "missing"}
        assert neuro["calendar"]["reason"]
        assert neuro["total_topics"] == 5

    def test_requires_a_token(self) -> None:
        assert configure().get("/v1/coordination").status_code == 401

    def test_skips_inactive_courses_and_absent_calendar_bindings(self, tmp_path: Path) -> None:
        _write_minimal_config(tmp_path, required=True, inactive_course=True)

        payload = configure(config_root=tmp_path).get("/v1/coordination", headers=AUTH).json()

        assert [course["course_code"] for course in payload["courses"]] == ["NEURO"]
        assert payload["inactive_course_codes"] == ["GASTRO"]
        assert payload["courses"][0]["calendar"]["status"] == "missing"
        assert payload["courses"][0]["calendar"]["calendar_id"] is None

    def test_reports_missing_configuration_without_a_filesystem_path(
        self,
        tmp_path: Path,
    ) -> None:
        response = configure(config_root=tmp_path).get("/v1/coordination", headers=AUTH)

        assert response.status_code == 404
        assert str(tmp_path) not in response.json()["detail"]


class TestScheduleEndpoint:
    """Verify planned class dates are served as planned, never as confirmed."""

    def test_returns_upcoming_planned_dates(self) -> None:
        response = configure().get("/v1/courses/neuro/schedule", headers=AUTH)

        assert response.status_code == 200
        payload = response.json()
        assert payload["course_code"] == "NEURO"
        assert payload["enabled"] is True
        assert len(payload["upcoming"]) <= 5
        assert {entry["weekday"] for entry in payload["upcoming"]} <= {"tuesday", "thursday"}
        assert "Calendar evidence this backend does not read" in payload["note"]

    def test_honours_the_requested_limit(self) -> None:
        payload = configure().get("/v1/courses/NEURO/schedule?limit=2", headers=AUTH).json()

        assert len(payload["upcoming"]) == 2

    @pytest.mark.parametrize("limit", ["0", "51", "many"])
    def test_rejects_an_unusable_limit(self, limit: str) -> None:
        response = configure().get(f"/v1/courses/NEURO/schedule?limit={limit}", headers=AUTH)

        assert response.status_code == 422

    def test_reports_an_unknown_course(self) -> None:
        response = configure().get("/v1/courses/CARDIO/schedule", headers=AUTH)

        assert response.status_code == 404
        assert "CARDIO" in response.json()["detail"]

    def test_requires_a_token(self) -> None:
        assert configure().get("/v1/courses/NEURO/schedule").status_code == 401
