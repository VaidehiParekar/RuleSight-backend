from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.auth import has_permission
from app.core.deps import get_current_actor, require_permission
from app.db.queries import (
    get_gap_sql,
    get_remediation_sql,
    list_remediations_sql,
    update_remediation_sql,
)
from app.db.session import get_session, write_transaction
from app.schemas.domain import Remediation, RemediationStatus, UserResponse

router = APIRouter(prefix="/remediations", tags=["remediations"])

# Moving a remediation into these states is an approval decision (remediations:approve).
APPROVAL_STATUSES = frozenset({"approved", "verified"})


class RemediationUpdateInput(BaseModel):
    status: RemediationStatus
    reason: str | None = None
    action: str | None = None
    owner_team: str | None = None


@router.get("", response_model=list[Remediation])
def list_remediations(
    _user: UserResponse = Depends(require_permission("remediations:read")),
    session: Session = Depends(get_session),
) -> list[Remediation]:
    """Lists active remediation plans."""
    return list_remediations_sql(session)


@router.patch("/{id}", response_model=Remediation)
def update_remediation(
    id: str,
    input_data: RemediationUpdateInput,
    user: UserResponse = Depends(require_permission("remediations:create")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> Remediation:
    """Updates remediation plan (e.g. approved by Officer) and records an audit log entry."""
    if input_data.status in APPROVAL_STATUSES and not has_permission(
        user.role, "remediations:approve"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access denied: permission 'remediations:approve' is required for this operation."
            ),
        )

    with write_transaction(session):
        before_rem = get_remediation_sql(session, id)
        if not before_rem:
            raise HTTPException(status_code=404, detail="Remediation not found")

        updated = update_remediation_sql(
            session,
            id,
            status=input_data.status,
            # Blank strings leave the current text unchanged (same as the UI's mock API).
            action=input_data.action or None,
            owner_team=input_data.owner_team or None,
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
