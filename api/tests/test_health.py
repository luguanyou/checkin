from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from attendance_api.main import create_app


def test_live_does_not_require_auth() -> None:
    response = TestClient(create_app()).get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_uses_api_title_and_version() -> None:
    schema = TestClient(create_app()).get("/openapi.json").json()

    assert schema["info"]["title"] == "智能课堂考勤 API"
    assert schema["info"]["version"] == "1.0.0"


def test_ready_checks_database() -> None:
    response = TestClient(create_app()).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_startup_runs_admin_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrap = Mock()
    monkeypatch.setattr("attendance_api.main.bootstrap_configured_admin", bootstrap)

    with TestClient(create_app()):
        pass

    bootstrap.assert_called_once_with()
