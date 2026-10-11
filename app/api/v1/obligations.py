from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, get_actor, record_audit
from app.db.queries import get_obligation_sql, list_obligations_sql, update_obligation_sql
from app.db.session import get_session
from app.schemas.domain import Obligation, ReviewStatus

router = APIRouter(prefix="/obligations", tags=["obligations"])


class ObligationUpdateInput(BaseModel):
    review_status: ReviewStatus | None = None
    reason: str | None = None
    fields: dict[str, Any] | None = None


@router.get("", response_model=list[Obligation])
def list_obligations(
    document_id: str | None = Query(None),
    applicability: str | None = Query(None),
    review_status: str | None = Query(None),
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
    actor: ActorInfo = Depends(get_actor),
    session: Session = Depends(get_session),
) -> Obligation:
    """Updates an obligation's review status or fields and records an audit entry."""
    with session.begin():
        before_ob = get_obligation_sql(session, id)
        if not before_ob:
            raise HTTPException(status_code=404, detail="Obligation not found")

        updated = update_obligation_sql(
            session,
            id,
            review_status=input_data.review_status,
            fields=input_data.fields,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Failed to update obligation")

        action_label = f"Updated obligation to {input_data.review_status}" if input_data.review_status else "Edited obligation"
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
