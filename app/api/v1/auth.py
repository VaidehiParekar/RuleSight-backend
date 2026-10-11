"""Authentication endpoints for RuleSight."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.auth import create_access_token, verify_password
from app.core.deps import (
    get_current_user,
    require_permission,
    role_label,
    user_response_from_row,
)
from app.db.queries import (
    get_user_by_email_sql,
    list_users_sql,
    update_user_last_login_sql,
)
from app.db.session import get_session, write_transaction
from app.schemas.domain import AuthResponse, LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.auth")


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
) -> AuthResponse:
    """Authenticates credentials, generates JWT bearer token, and updates last login timestamp."""
    user = get_user_by_email_sql(session, payload.email)
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    user_id = user["id"]
    role = user["role"]
    token = create_access_token(
        {
            "sub": user_id,
            "email": user["email"],
            "role": role,
        }
    )
    user_resp = user_response_from_row(user)

    with write_transaction(session):
        update_user_last_login_sql(session, user_id)
        # The audit entry is written in a savepoint: if it fails the failure is logged and the
        # sign-in (and last_login_at) still commits.
        try:
            with session.begin_nested():
                record_audit(
                    session=session,
                    actor=ActorInfo(name=user["full_name"], role=role_label(role)),
                    action="Logged in to platform",
                    entity_type="session",
                    entity_code=user_id,
                    before=None,
                    after={"email": user["email"], "role": role},
                )
        except Exception:
            logger.exception("Could not record the login audit entry for user %s", user_id)

    return AuthResponse(access_token=token, token_type="bearer", user=user_resp)  # noqa: S106


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Returns profile and permissions for the currently authenticated user."""
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    _user: UserResponse = Depends(require_permission("users:manage")),
    session: Session = Depends(get_session),
) -> list[UserResponse]:
    """Lists all user accounts. Administrators only."""
    return [user_response_from_row(u) for u in list_users_sql(session)]
