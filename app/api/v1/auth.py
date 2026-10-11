"""Authentication endpoints for RuleSight."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.auth import create_access_token, get_role_permissions, verify_password
from app.core.deps import get_current_user
from app.db.queries import (
    get_user_by_email_sql,
    list_users_sql,
    update_user_last_login_sql,
)
from app.db.session import get_session
from app.schemas.domain import AuthResponse, LoginRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


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
    update_user_last_login_sql(session, user_id)

    # Issue JWT token
    token = create_access_token({
        "sub": user_id,
        "email": user["email"],
        "role": role,
    })

    user_resp = UserResponse(
        id=user_id,
        email=user["email"],
        full_name=user["full_name"],
        role=role,
        initials=user["initials"],
        is_active=user["is_active"],
        created_at=user.get("created_at"),
        last_login_at=user.get("last_login_at"),
        permissions=get_role_permissions(role),
    )

    # Record login audit entry
    try:
        record_audit(
            session=session,
            actor=ActorInfo(name=user["full_name"], role=role),
            action="Logged in to platform",
            entity_type="session",
            entity_code=user_id,
            before=None,
            after={"email": user["email"], "role": role},
        )
        session.commit()
    except Exception:
        session.rollback()

    return AuthResponse(access_token=token, token_type="bearer", user=user_resp)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Returns profile and permissions for the currently authenticated user."""
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_demo_users(
    session: Session = Depends(get_session),
) -> list[UserResponse]:
    """Returns available users for demo persona switching and admin inspection."""
    users = list_users_sql(session)
    return [
        UserResponse(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            role=u["role"],
            initials=u["initials"],
            is_active=u["is_active"],
            created_at=u.get("created_at"),
            last_login_at=u.get("last_login_at"),
            permissions=get_role_permissions(u["role"]),
        )
        for u in users
    ]
