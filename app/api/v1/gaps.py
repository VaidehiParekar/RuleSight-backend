import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, get_actor, record_audit
from app.core.rules import calculate_risk, evaluate_gap_type
from app.db.queries import (
    get_gap_sql,
    get_gap_trace_sql,
    list_gaps_sql,
    update_gap_status_sql,
)
from app.db.session import get_session
from app.schemas.domain import (
    Applicability,
    Coverage,
    DesignAssessment,
    Gap,
    GapStatus,
    GapTrace,
    GapType,
    OperatingAssessment,
    Priority,
    Remediation,
    RiskFactors,
)

router = APIRouter(prefix="/gaps", tags=["gaps"])


class GapUpdateInput(BaseModel):
    status: GapStatus
    reason: str | None = None


class EvaluateGapInput(BaseModel):
    applicability: Applicability = "applicable"
    mappings_coverage: list[Coverage] = Field(default_factory=list)
    design: DesignAssessment | None = None
    operating: OperatingAssessment | None = None
    topic: str = "financial_crime"
    origin: Literal["initial", "change"] = "initial"


class EvaluateGapResponse(BaseModel):
    has_gap: bool
    gap_type: GapType | None = None
    risk_score: float | None = None
    priority: Priority | None = None
    risk_factors: RiskFactors | None = None


@router.post("/evaluate", response_model=EvaluateGapResponse)
def evaluate_gap_rule(input_data: EvaluateGapInput) -> EvaluateGapResponse:
    """Evaluates the 5-rule deterministic decision tree and calculates risk score using app.core.rules."""
    gap_type = evaluate_gap_type(
        applicability=input_data.applicability,
        mappings_coverage=input_data.mappings_coverage,
        design=input_data.design,
        operating=input_data.operating,
    )
    if not gap_type:
        return EvaluateGapResponse(has_gap=False)

    score, priority, factors = calculate_risk(
        topic=input_data.topic,
        gap_type=gap_type,
        origin=input_data.origin,
    )
    return EvaluateGapResponse(
        has_gap=True,
        gap_type=gap_type,
        risk_score=score,
        priority=priority,
        risk_factors=factors,
    )


@router.get("", response_model=list[Gap])
def list_gaps(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    session: Session = Depends(get_session),
) -> list[Gap]:
    """Lists compliance gaps sorted by risk_score DESC."""
    return list_gaps_sql(session, status=status, priority=priority)


@router.get("/{id}", response_model=Gap)
def get_gap(id: str, session: Session = Depends(get_session)) -> Gap:
    gap = get_gap_sql(session, id)
    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")
    return gap


@router.get("/{id}/trace", response_model=GapTrace)
def get_gap_trace(id: str, session: Session = Depends(get_session)) -> GapTrace:
    """The Money Screen: returns the full 9-step proof chain from clause to remediation and audit."""
    trace = get_gap_trace_sql(session, id)
    if not trace:
        raise HTTPException(status_code=404, detail="Gap trace not found")
    return trace


@router.patch("/{id}", response_model=Gap)
def update_gap(
    id: str,
    input_data: GapUpdateInput,
    actor: ActorInfo = Depends(get_actor),
    session: Session = Depends(get_session),
) -> Gap:
    """Updates gap status (potential, confirmed, dismissed) and records audit log."""
    with session.begin():
        before_gap = get_gap_sql(session, id)
        if not before_gap:
            raise HTTPException(status_code=404, detail="Gap not found")

        updated = update_gap_status_sql(session, id, input_data.status, reason=input_data.reason)
        if not updated:
            raise HTTPException(status_code=404, detail="Failed to update gap")

        record_audit(
            session,
            actor=actor,
            action=f"Updated gap to {input_data.status}",
            entity_type="gap",
            entity_code=updated.code,
            before={"status": before_gap.status},
            after={"status": updated.status},
            reason=input_data.reason,
        )

    return updated


@router.post("/{id}/recalculate-risk", response_model=Gap)
def recalculate_gap_risk(
    id: str,
    actor: ActorInfo = Depends(get_actor),
    session: Session = Depends(get_session),
) -> Gap:
    """Recomputes risk score and priority for a gap using the app.core.rules formula."""
    with session.begin():
        gap = get_gap_sql(session, id)
        if not gap:
            raise HTTPException(status_code=404, detail="Gap not found")

        topic = gap.title or "regulatory"
        score, priority, factors = calculate_risk(
            topic=topic,
            gap_type=gap.gap_type,
            origin="initial",
        )

        query = text("""
            UPDATE gaps
            SET risk_score = :risk_score,
                priority = :priority,
                risk_factors = CAST(:risk_factors AS jsonb),
                updated_at = now()
            WHERE id = :id
            RETURNING *
        """)
        row = session.execute(
            query,
            {
                "id": id,
                "risk_score": score,
                "priority": priority,
                "risk_factors": factors.model_dump_json(),
            },
        ).mappings().first()

        record_audit(
            session,
            actor=actor,
            action="Recalculated gap risk",
            entity_type="gap",
            entity_code=gap.code,
            before={"risk_score": gap.risk_score, "priority": gap.priority},
            after={"risk_score": score, "priority": priority},
        )

        return Gap.model_validate(dict(row))


@router.post("/{id}/remediation", response_model=Remediation)
def create_remediation_draft(
    id: str,
    actor: ActorInfo = Depends(get_actor),
    session: Session = Depends(get_session),
) -> Remediation:
    """Drafts an AI-assisted remediation task for a compliance gap."""
    with session.begin():
        gap = get_gap_sql(session, id)
        if not gap:
            raise HTTPException(status_code=404, detail="Gap not found")

        rem_id = f"rem-{uuid.uuid4().hex[:6]}"
        action = f"Remediate {gap.title}: update internal procedures and clear backlogged accounts."
        owner_team = "Compliance Operations"
        target_days = 30
        closure_evidence = "Updated SOP and signed test logs demonstrating compliance."

        query = text("""
            INSERT INTO remediations (
                id, gap_id, action, owner_team, target_days, closure_evidence, status
            ) VALUES (
                :id, :gap_id, :action, :owner_team, :target_days, :closure_evidence, 'draft'
            )
            RETURNING *
        """)
        row = session.execute(
            query,
            {
                "id": rem_id,
                "gap_id": gap.id,
                "action": action,
                "owner_team": owner_team,
                "target_days": target_days,
                "closure_evidence": closure_evidence,
            },
        ).mappings().first()

        record_audit(
            session,
            actor=actor,
            action="Drafted remediation",
            entity_type="remediation",
            entity_code=gap.code,
            before=None,
            after={"status": "draft", "action": action},
        )

        return Remediation.model_validate(dict(row))
