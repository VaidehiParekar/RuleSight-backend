import re
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import auth as auth_module
from app.core.auth import create_access_token, get_role_permissions
from app.core.config import get_settings
from app.db.session import get_session
from tests.conftest import TEST_DATABASE_URL

# Endpoints that must stay reachable without signing in.
PUBLIC_ROUTES = {
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/health/ready"),
    ("POST", "/api/v1/auth/login"),
}

USERS: dict[str, dict[str, Any]] = {
    "usr-officer": {
        "id": "usr-officer",
        "email": "officer@example.test",
        "full_name": "Test Officer",
        "role": "compliance_officer",
        "initials": "TO",
        "is_active": True,
        "created_at": None,
        "last_login_at": None,
    },
    "usr-auditor": {
        "id": "usr-auditor",
        "email": "auditor@example.test",
        "full_name": "Test Auditor",
        "role": "auditor",
        "initials": "TA",
        "is_active": True,
        "created_at": None,
        "last_login_at": None,
    },
}


@pytest.fixture(autouse=True)
def _signing_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Tokens are signed with get_settings(); pin its inputs so no local .env value matters.
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-signing-key-that-is-long-enough-1234")
    get_settings.cache_clear()
    auth_module._signing_key.cache_clear()
    yield
    auth_module._signing_key.cache_clear()


@pytest.fixture
def api(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client with a fake database session and a fake users table (USERS)."""

    def _fake_session() -> Iterator[Session]:
        yield MagicMock(spec=Session)

    app.dependency_overrides[get_session] = _fake_session
    monkeypatch.setattr(
        "app.core.deps.get_user_by_id_sql", lambda _session, user_id: USERS.get(user_id)
    )
    monkeypatch.setattr("app.api.v1.controls.list_controls_sql", lambda _session: [])
    monkeypatch.setattr("app.api.v1.auth.list_users_sql", lambda _session: list(USERS.values()))
    return TestClient(app)


def _bearer(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


def test_request_without_token_is_401(api: TestClient) -> None:
    response = api.get("/api/v1/controls")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_x_actor_header_is_not_a_sign_in(api: TestClient) -> None:
    response = api.get("/api/v1/controls", headers={"X-Actor": "Priya Sharma"})

    assert response.status_code == 401


def test_tampered_token_is_401(api: TestClient) -> None:
    response = api.get("/api/v1/controls", headers={"Authorization": "Bearer not.a.token"})

    assert response.status_code == 401


def test_valid_token_for_unknown_or_inactive_user_is_401(api: TestClient) -> None:
    # The users query excludes inactive accounts, so both look like "no such user".
    response = api.get("/api/v1/controls", headers=_bearer("usr-deleted"))

    assert response.status_code == 401


def test_valid_token_with_permission_is_200(api: TestClient) -> None:
    response = api.get("/api/v1/controls", headers=_bearer("usr-auditor"))

    assert response.status_code == 200
    assert response.json() == []


def test_missing_permission_is_403(api: TestClient) -> None:
    response = api.patch(
        "/api/v1/obligations/ob-1",
        json={"review_status": "accepted"},
        headers=_bearer("usr-auditor"),
    )

    assert response.status_code == 403
    assert "obligations:edit" in response.json()["detail"]


def test_user_list_requires_users_manage(api: TestClient) -> None:
    response = api.get("/api/v1/auth/users", headers=_bearer("usr-officer"))

    assert response.status_code == 403


def test_me_returns_profile_with_role_permissions(api: TestClient) -> None:
    response = api.get("/api/v1/auth/me", headers=_bearer("usr-officer"))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "officer@example.test"
    assert body["role"] == "compliance_officer"
    assert body["permissions"] == get_role_permissions("compliance_officer")


def test_every_non_public_route_rejects_anonymous_requests(api: TestClient, app: FastAPI) -> None:
    checked = 0
    for route_path, operations in app.openapi()["paths"].items():
        path = re.sub(r"\{[^}]+\}", "x", route_path)
        for method in operations:
            if (method.upper(), route_path) in PUBLIC_ROUTES:
                continue
            response = api.request(method.upper(), path)
            assert response.status_code == 401, f"{method} {route_path} -> {response.status_code}"
            checked += 1
    assert checked > 20
