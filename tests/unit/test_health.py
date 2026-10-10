from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import override_session


def test_liveness_returns_ok_without_touching_the_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_is_ok_when_database_is_reachable(app: FastAPI) -> None:
    override_session(app, reachable=True)

    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readiness_returns_safe_503_when_database_is_down(app: FastAPI) -> None:
    override_session(app, reachable=False)

    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["message"] == "The database is unavailable."
    # The driver error (host, user) must never reach the client.
    assert "10.0.0.5" not in response.text
    assert "test_user" not in response.text


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["X-Request-ID"]


def test_valid_incoming_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc.123"})

    assert response.headers["X-Request-ID"] == "trace-abc.123"


def test_unsafe_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "bad id<script>"})

    assert response.headers["X-Request-ID"] != "bad id<script>"
    assert len(response.headers["X-Request-ID"]) == 32


def test_security_headers_are_set(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_cors_allows_only_the_configured_frontend_origin(client: TestClient) -> None:
    allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    denied = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_openapi_is_available_outside_production(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert "/api/v1/health/ready" in response.json()["paths"]
