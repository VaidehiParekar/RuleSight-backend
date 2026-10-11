from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.queries import list_audit_sql
from app.db.session import get_session
from app.schemas.domain import AuditEntry

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEntry])
def list_audit(
    entity_code: str | None = Query(None),
    actor: str | None = Query(None),
    limit: int = Query(100),
    session: Session = Depends(get_session),
) -> list[AuditEntry]:
    """Lists immutable audit log entries recording actor decisions and before/after states."""
    return list_audit_sql(session, entity_code=entity_code, actor=actor, limit=limit)
