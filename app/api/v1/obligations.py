from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.deps import get_current_actor, require_permission
from app.db.queries import get_obligation_sql, list_obligations_sql, update_obligation_sql
from app.db.session import get_session, write_transaction
from app.schemas.domain import Applicability, Obligation, ReviewStatus, UserResponse

router = APIRouter(prefix="/obligations", tags=["obligations"])


class ObligationFieldsInput(BaseModel):
    """The editable parts of an obligation. Only the keys that are sent are changed."""

    model_config = ConfigDict(extra="forbid")

    action: str | None = None
    frequency: str | None = None
    deadline: str | None = None
    threshold: str | None = None
    condition: str | None = None


class ObligationUpdateInput(BaseModel):
    review_status: ReviewStatus
    reason: str | None = None
    fields: ObligationFieldsInput | None = None


@router.get("", response_model=list[Obligation])
def list_obligations(
    document_id: str | None = Query(None),
    applicability: Applicability | None = Query(None),
    review_status: ReviewStatus | None = Query(None),
    _user: UserResponse = Depends(require_permission("obligations:read")),
    session: Session = Depends(get_session),
) -> list[Obligation]:
    """Lists regulatory obligations with verbatim quotes and applicability status."""
    return list_obligations_sql(
        session,
        document_id=document_id,
        applicability=applicability,
        review_status=review_status,
    )


@router.get("/{id}", response_model=Obligation)
def get_obligation(
    id: str,
    _user: UserResponse = Depends(require_permission("obligations:read")),
    session: Session = Depends(get_session),
) -> Obligation:
    obligation = get_obligation_sql(session, id)
    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return obligation


@router.patch("/{id}", response_model=Obligation)
def update_obligation(
    id: str,
    input_data: ObligationUpdateInput,
    _user: UserResponse = Depends(require_permission("obligations:edit")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> Obligation:
    """Updates an obligation's review status or fields and records an audit entry."""
    with write_transaction(session):
        before_ob = get_obligation_sql(session, id)
        if not before_ob:
            raise HTTPException(status_code=404, detail="Obligation not found")

        updated = update_obligation_sql(
            session,
            id,
            review_status=input_data.review_status,
            fields=input_data.fields.model_dump(exclude_unset=True) if input_data.fields else None,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Failed to update obligation")

        action_label = f"Updated obligation to {input_data.review_status}"
        record_audit(
            session,
            actor=actor,
            action=action_label,
            entity_type="obligation",
            entity_code=updated.code,
            before={"review_status": before_ob.review_status},
            after={"review_status": updated.review_status},
            reason=input_data.reason,
        )

    return updated
