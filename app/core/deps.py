"""FastAPI dependencies for authentication, RBAC authorization, and actor propagation.

Every endpoint except the health probes and POST /auth/login requires a valid Bearer token
(see ``require_permission``). There is no header-based or anonymous fallback.
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo
from app.core.auth import decode_access_token, get_role_permissions, has_permission
from app.db.queries import get_user_by_id_sql
from app.db.session import get_session
from app.schemas.domain import UserResponse

_BEARER_PREFIX = "bearer "


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def user_response_from_row(user_data: dict[str, Any]) -> UserResponse:
    """Builds the public user profile (with role permissions) from a users row."""
    role = user_data["role"]
    return UserResponse(
        id=user_data["id"],
        email=user_data["email"],
        full_name=user_data["full_name"],
        role=role,
        initials=user_data["initials"],
        is_active=user_data["is_active"],
        created_at=user_data.get("created_at"),
        last_login_at=user_data.get("last_login_at"),
        permissions=get_role_permissions(role),
    )


def role_label(role: str) -> str:
    """Human-readable role for the audit trail, e.g. compliance_officer -> Compliance Officer."""
    return role.replace("_", " ").title()


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Returns the signed-in user from the Bearer token, or raises 401."""
    if not authorization or not authorization.lower().startswith(_BEARER_PREFIX):
        raise _unauthorized("Sign in required.")

    token = authorization[len(_BEARER_PREFIX) :].strip()
    payload = decode_access_token(token) if token else None
    user_id = payload.get("sub") if payload else None
    if not user_id:
        raise _unauthorized("Invalid or expired authentication token.")

    # Inactive users are excluded by the query: a valid signature alone is not a sign-in.
    user_data = get_user_by_id_sql(session, str(user_id))
    if not user_data:
        raise _unauthorized("Invalid or expired authentication token.")
    return user_response_from_row(user_data)


def get_current_actor(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> ActorInfo:
    """Provides ActorInfo for the audit trail based on the authenticated user."""
    return ActorInfo(name=current_user.full_name, role=role_label(current_user.role))


def require_permission(permission: str) -> Callable[..., UserResponse]:
    """Dependency factory: 401 without a valid token, 403 when the role lacks ``permission``."""

    def dependency(
        current_user: Annotated[UserResponse, Depends(get_current_user)],
    ) -> UserResponse:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: permission '{permission}' is required for this operation.",
            )
        return current_user

    return dependency
