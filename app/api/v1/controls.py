from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.queries import get_control_sql, list_controls_sql
from app.db.session import get_session
from app.schemas.domain import Control, UserResponse

router = APIRouter(prefix="/controls", tags=["controls"])


@router.get("", response_model=list[Control])
def list_controls(
    _user: UserResponse = Depends(require_permission("controls:read")),
    session: Session = Depends(get_session),
) -> list[Control]:
    """Lists institutional controls parsed from internal bank policies and RCM."""
    return list_controls_sql(session)


@router.get("/{id}", response_model=Control)
def get_control(
    id: str,
    _user: UserResponse = Depends(require_permission("controls:read")),
    session: Session = Depends(get_session),
) -> Control:
    control = get_control_sql(session, id)
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")
    return control
