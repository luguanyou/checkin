from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel

from attendance_api.main import create_app


def test_unknown_route_uses_uniform_error() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/not-found", headers={"X-Request-ID": "req_test"}
    )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "req_test"
    assert response.json() == {
        "code": "RESOURCE_NOT_FOUND",
        "message": "请求的资源不存在",
        "details": {},
        "request_id": "req_test",
    }


def test_invalid_request_id_is_replaced() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/health/live", headers={"X-Request-ID": "x" * 65}
    )

    request_id = response.headers["X-Request-ID"]
    assert request_id.startswith("req_")
    assert request_id != "x" * 65


def test_validation_error_uses_uniform_error() -> None:
    class Payload(BaseModel):
        count: int

    app = create_app()

    @app.post("/test-validation")
    def validate_payload(payload: Payload) -> dict[str, Any]:
        return payload.model_dump()

    response = TestClient(app).post(
        "/test-validation",
        json={"count": "not-a-number"},
        headers={"X-Request-ID": "req_validation"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"
    assert response.json()["message"] == "请求参数无效"
    assert response.json()["request_id"] == "req_validation"
    assert response.json()["details"]["errors"]


def test_unhandled_error_does_not_leak_internal_details() -> None:
    app = create_app()

    @app.get("/test-error")
    def raise_error() -> None:
        raise RuntimeError("secret database path")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/test-error", headers={"X-Request-ID": "req_internal"}
    )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "req_internal"
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "服务器内部错误",
        "details": {},
        "request_id": "req_internal",
    }
    assert "secret" not in response.text
