from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import NotFoundError


class _Payload(BaseModel):
    count: int


def _app_with_probe_routes(app: FastAPI) -> FastAPI:
    @app.get("/api/v1/probe/not-found")
    def not_found() -> None:
        raise NotFoundError()

    @app.get("/api/v1/probe/crash")
    def crash() -> None:
        raise RuntimeError("secret internal detail: password=hunter2")

    @app.post("/api/v1/probe/validate")
    def validate(payload: _Payload) -> dict[str, int]:
        return {"count": payload.count}

    return app


def test_domain_errors_use_the_standard_envelope(app: FastAPI) -> None:
    client = TestClient(_app_with_probe_routes(app))

    response = client.get("/api/v1/probe/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "The requested resource was not found."
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_unexpected_errors_return_a_generic_500(app: FastAPI) -> None:
    client = TestClient(_app_with_probe_routes(app), raise_server_exceptions=False)

    response = client.get("/api/v1/probe/crash")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["message"] == "An unexpected error occurred."
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "hunter2" not in response.text


def test_validation_errors_report_fields_but_not_input_values(app: FastAPI) -> None:
    client = TestClient(_app_with_probe_routes(app))

    response = client.post("/api/v1/probe/validate", json={"count": "super-secret-value"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"][0]["field"] == "body.count"
    assert "super-secret-value" not in response.text
