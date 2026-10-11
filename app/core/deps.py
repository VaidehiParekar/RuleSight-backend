"""FastAPI dependencies for authentication, RBAC authorization, and actor propagation."""

from typing import Annotated, Callable
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo
from app.core.auth import decode_access_token, get_role_permissions, has_permission
from app.db.queries import get_user_by_email_sql, get_user_by_id_sql
from app.db.session import get_session
from app.schemas.domain import UserResponse


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_actor: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Extracts the authenticated user from the Bearer token, or falls back to X-Actor."""
    # 1. Bearer Token Authentication
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = payload.get("sub")
        if user_id:
            user_data = get_user_by_id_sql(session, user_id)
            if user_data:
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

    # 2. Backward compatibility fallback via X-Actor header
    actor_str = (x_actor or "").strip().lower()
    fallback_email = "priya@rulesight.bank"
    if "rahul" in actor_str:
        fallback_email = "rahul@rulesight.bank"
    elif "admin" in actor_str:
        fallback_email = "admin@rulesight.bank"
    elif "auditor" in actor_str or "ananya" in actor_str:
        fallback_email = "auditor@rbi.gov.in"

    user_data = get_user_by_email_sql(session, fallback_email)
    if user_data:
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

    # In-memory emergency fallback if DB has not been seeded
    return UserResponse(
        id="usr-priya",
        email="priya@rulesight.bank",
        full_name="Priya Sharma",
        role="compliance_officer",
        initials="PS",
        is_active=True,
        permissions=get_role_permissions("compliance_officer"),
    )


def get_current_actor(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> ActorInfo:
    """Provides ActorInfo for the audit trail based on authenticated user."""
    return ActorInfo(name=current_user.full_name, role=current_user.role)


def require_permission(permission: str) -> Callable:
    """Dependency factory that verifies the authenticated user possesses a given permission."""
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


def require_roles(allowed_roles: list[str]) -> Callable:
    """Dependency factory that checks if user's role is in the allowed roles list."""
    def dependency(
        current_user: Annotated[UserResponse, Depends(get_current_user)],
    ) -> UserResponse:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: required role must be one of {allowed_roles}.",
            )
        return current_user

    return dependency
