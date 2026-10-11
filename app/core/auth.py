"""Authentication, JWT token lifecycle, password hashing, and RBAC permissions."""

import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _signing_key() -> str:
    """JWT signing key from JWT_SECRET_KEY, or a random per-process key in development."""
    configured = get_settings().jwt_secret_key
    return configured.get_secret_value() if configured else secrets.token_urlsafe(48)


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "users:manage",
        "pipeline:run",
        "documents:read",
        "documents:upload",
        "obligations:read",
        "obligations:edit",
        "mappings:read",
        "mappings:verify",
        "controls:read",
        "gaps:read",
        "gaps:signoff",
        "gaps:dismiss",
        "remediations:read",
        "remediations:create",
        "remediations:approve",
        "changes:read",
        "changes:compare",
        "graph:read",
        "eval:read",
        "audit:read",
    ],
    "compliance_officer": [
        "pipeline:run",
        "documents:read",
        "documents:upload",
        "obligations:read",
        "obligations:edit",
        "mappings:read",
        "mappings:verify",
        "controls:read",
        "gaps:read",
        "gaps:signoff",
        "gaps:dismiss",
        "remediations:read",
        "remediations:create",
        "remediations:approve",
        "changes:read",
        "changes:compare",
        "graph:read",
        "eval:read",
        "audit:read",
    ],
    "compliance_analyst": [
        "documents:read",
        "documents:upload",
        "obligations:read",
        "obligations:edit",
        "mappings:read",
        "mappings:verify",
        "controls:read",
        "gaps:read",
        "remediations:read",
        "remediations:create",
        "changes:read",
        "changes:compare",
        "graph:read",
        "eval:read",
        "audit:read",
    ],
    "auditor": [
        "documents:read",
        "obligations:read",
        "mappings:read",
        "controls:read",
        "gaps:read",
        "remediations:read",
        "changes:read",
        "changes:compare",
        "graph:read",
        "eval:read",
        "audit:read",
    ],
}


def get_role_permissions(role: str) -> list[str]:
    """Returns the granular permissions assigned to a given role."""
    return ROLE_PERMISSIONS.get(role, [])


def has_permission(role: str, permission: str) -> bool:
    """Checks whether a given role holds a specific permission."""
    perms = get_role_permissions(role)
    return permission in perms or "users:manage" in perms


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=get_settings().jwt_expire_minutes)

    to_encode.update({"iat": now, "exp": expire})
    encoded_jwt = jwt.encode(to_encode, _signing_key(), algorithm=get_settings().jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, _signing_key(), algorithms=[get_settings().jwt_algorithm])
        return payload
    except jwt.PyJWTError:
        return None
