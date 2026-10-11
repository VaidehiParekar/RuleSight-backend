from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, get_actor, record_audit
from app.db.queries import (
    get_gap_sql,
    get_remediation_sql,
    list_remediations_sql,
    update_remediation_sql,
)
from app.db.session import get_session
from app.schemas.domain import Remediation, RemediationStatus

router = APIRouter(prefix="/remediations", tags=["remediations"])


class RemediationUpdateInput(BaseModel):
    status: RemediationStatus
    reason: str | None = None
    action: str | None = None
    owner_team: str | None = None


@router.get("", response_model=list[Remediation])
def list_remediations(session: Session = Depends(get_session)) -> list[Remediation]:
    """Lists active remediation plans."""
    return list_remediations_sql(session)


@router.patch("/{id}", response_model=Remediation)
def update_remediation(
    id: str,
    input_data: RemediationUpdateInput,
    actor: ActorInfo = Depends(get_actor),
    session: Session = Depends(get_session),
) -> Remediation:
    """Updates remediation plan (e.g. approved by Officer) and records an audit log entry."""
    with session.begin():
        before_rem = get_remediation_sql(session, id)
        if not before_rem:
            raise HTTPException(status_code=404, detail="Remediation not found")

        updated = update_remediation_sql(
            session,
            id,
            status=input_data.status,
            action=input_data.action,
            owner_team=input_data.owner_team,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Failed to update remediation")

        gap = get_gap_sql(session, updated.gap_id)
        entity_code = gap.code if gap else updated.id

        record_audit(
            session,
            actor=actor,
            action=f"Updated remediation to {input_data.status}",
            entity_type="remediation",
            entity_code=entity_code,
            before={"status": before_rem.status},
            after={"status": updated.status},
            reason=input_data.reason,
        )

    return updated
