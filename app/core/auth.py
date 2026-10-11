"""Authentication, JWT token lifecycle, password hashing, and RBAC permissions."""

from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
import jwt

# Fallback secret for local development / testing
JWT_SECRET_KEY = "rulesight-super-secret-jwt-key-2026-hackathon-et-ai"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


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
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"iat": now, "exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
