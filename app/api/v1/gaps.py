import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.auth import has_permission
from app.core.config import get_settings
from app.core.deps import get_current_actor, require_permission
from app.core.rules import calculate_risk, evaluate_gap_type
from app.db.queries import (
    get_control_sql,
    get_gap_sql,
    get_gap_trace_sql,
    get_obligation_sql,
    list_gaps_sql,
    update_gap_status_sql,
)
from app.db.session import get_session, write_transaction
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
    UserResponse,
)

router = APIRouter(prefix="/gaps", tags=["gaps"])

# Dismissing a gap needs its own permission; every other status change is a sign-off decision.
_STATUS_PERMISSION: dict[str, str] = {"dismissed": "gaps:dismiss"}
_DEFAULT_STATUS_PERMISSION = "gaps:signoff"


class GapUpdateInput(BaseModel):
    status: GapStatus
    reason: str | None = None


class EvaluateGapInput(BaseModel):
    applicability: Applicability = "applicable"
    mappings_coverage: list[Coverage] = Field(default_factory=list)
    design: DesignAssessment | None = None
    operating: OperatingAssessment | None = None
    topic: str
    origin: Literal["initial", "change"] = "initial"


class EvaluateGapResponse(BaseModel):
    has_gap: bool
    gap_type: GapType | None = None
    risk_score: float | None = None
    priority: Priority | None = None
    risk_factors: RiskFactors | None = None


@router.post("/evaluate", response_model=EvaluateGapResponse)
def evaluate_gap_rule(
    input_data: EvaluateGapInput,
    _user: UserResponse = Depends(require_permission("gaps:read")),
) -> EvaluateGapResponse:
    """Runs the 5-rule gap decision tree and the risk formula (app.core.rules)."""
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
    status: GapStatus | None = Query(None),
    priority: Priority | None = Query(None),
    _user: UserResponse = Depends(require_permission("gaps:read")),
    session: Session = Depends(get_session),
) -> list[Gap]:
    """Lists compliance gaps sorted by risk_score DESC."""
    return list_gaps_sql(session, status=status, priority=priority)


@router.get("/{id}", response_model=Gap)
def get_gap(
    id: str,
    _user: UserResponse = Depends(require_permission("gaps:read")),
    session: Session = Depends(get_session),
) -> Gap:
    gap = get_gap_sql(session, id)
    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")
    return gap


@router.get("/{id}/trace", response_model=GapTrace)
def get_gap_trace(
    id: str,
    _user: UserResponse = Depends(require_permission("gaps:read")),
    session: Session = Depends(get_session),
) -> GapTrace:
    """The Money Screen: the full proof chain from clause to remediation and audit."""
    trace = get_gap_trace_sql(session, id)
    if not trace:
        raise HTTPException(status_code=404, detail="Gap trace not found")
    return trace


@router.patch("/{id}", response_model=Gap)
def update_gap(
    id: str,
    input_data: GapUpdateInput,
    user: UserResponse = Depends(require_permission("gaps:read")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> Gap:
    """Updates gap status (potential, confirmed, dismissed, needs_info) and records audit log."""
    needed = _STATUS_PERMISSION.get(input_data.status, _DEFAULT_STATUS_PERMISSION)
    if not has_permission(user.role, needed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: permission '{needed}' is required for this operation.",
        )

    with write_transaction(session):
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
    _user: UserResponse = Depends(require_permission("gaps:signoff")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> Gap:
    """Recomputes risk score and priority for a gap using the app.core.rules formula."""
    with write_transaction(session):
        gap = get_gap_sql(session, id)
        if not gap:
            raise HTTPException(status_code=404, detail="Gap not found")
        obligation = get_obligation_sql(session, gap.obligation_id)
        if not obligation:
            raise HTTPException(status_code=404, detail="Obligation for this gap not found")

        # Keep the urgency that came from a regulatory change; the topic drives criticality.
        score, priority, factors = calculate_risk(
            topic=obligation.topic,
            gap_type=gap.gap_type,
            origin=gap.origin,
        )

        query = text("""
            UPDATE gaps
            SET risk_score = :risk_score,
                priority = :priority,
                risk_factors = CAST(:risk_factors AS jsonb)
            WHERE id = :id
        """)
        session.execute(
            query,
            {
                "id": id,
                "risk_score": score,
                "priority": priority,
                "risk_factors": factors.model_dump_json(),
            },
        )

        record_audit(
            session,
            actor=actor,
            action="Recalculated gap risk",
            entity_type="gap",
            entity_code=gap.code,
            before={"risk_score": gap.risk_score, "priority": gap.priority},
            after={"risk_score": score, "priority": priority},
        )
        updated = get_gap_sql(session, id)

    if not updated:
        raise HTTPException(status_code=404, detail="Gap not found")
    return updated


@router.post("/{id}/remediation", response_model=Remediation)
def create_remediation_draft(
    id: str,
    _user: UserResponse = Depends(require_permission("remediations:create")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> Remediation:
    """Drafts a remediation task for a gap from its obligation and involved controls.

    The owner and closure evidence come from the gap's controls; Settings supply the defaults
    when the gap has no control (for example a missing-control gap).
    """
    settings = get_settings()
    with write_transaction(session):
        gap = get_gap_sql(session, id)
        if not gap:
            raise HTTPException(status_code=404, detail="Gap not found")
        obligation = get_obligation_sql(session, gap.obligation_id)

        controls = [c for c in (get_control_sql(session, cid) for cid in gap.control_ids) if c]
        owner_team = next(
            (c.owner for c in controls if c.owner), settings.remediation_default_owner_team
        )
        closure_evidence = (
            "; ".join(dict.fromkeys(c.evidence_expected for c in controls if c.evidence_expected))
            or settings.remediation_default_closure_evidence
        )
        requirement = obligation.action if obligation else gap.description
        action = f"Close {gap.code} ({gap.title}): {requirement}"

        rem_id = f"rem-{uuid.uuid4().hex[:6]}"
        query = text("""
            INSERT INTO remediations (
                id, gap_id, action, owner_team, target_days, closure_evidence, status
            ) VALUES (
                :id, :gap_id, :action, :owner_team, :target_days, :closure_evidence, 'draft'
            )
            RETURNING *
        """)
        row = (
            session.execute(
                query,
                {
                    "id": rem_id,
                    "gap_id": gap.id,
                    "action": action,
                    "owner_team": owner_team,
                    "target_days": settings.remediation_default_target_days,
                    "closure_evidence": closure_evidence,
                },
            )
            .mappings()
            .first()
        )

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
