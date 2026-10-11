"""Raw parameterized SQL queries for the RuleSight database.

All database queries are defined here as parameterized SQL statements for safety and speed.
Results are mapped directly into Pydantic domain models from app.schemas.domain.
"""

import json
from datetime import datetime
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.domain import (
    AgentRun,
    Assessment,
    AuditEntry,
    ChangeComparisonResponse,
    Control,
    DashboardSummary,
    Evidence,
    Gap,
    GapTrace,
    Mapping,
    MissingCircular,
    Obligation,
    RegulatoryChange,
    Remediation,
    RunNode,
    SourceDocument,
)


# ---- Documents ---------------------------------------------------------------------------------

def list_documents_sql(session: Session) -> list[SourceDocument]:
    query = text("""
        SELECT d.*,
               COALESCE((SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.id), 0) AS chunk_count,
               COALESCE((SELECT COUNT(*) FROM obligations o WHERE o.document_id = d.id), 0) AS obligation_count
        FROM documents d
        ORDER BY d.created_at DESC
    """)
    rows = session.execute(query).mappings().all()
    results: list[SourceDocument] = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() if isinstance(d["created_at"], datetime) else str(d["created_at"])
        d["sha256"] = d.get("sha256") or ""
        d["reference"] = d.get("reference") or ""
        results.append(SourceDocument.model_validate(d))
    return results


def get_document_sql(session: Session, doc_id: str) -> SourceDocument | None:
    query = text("""
        SELECT d.*,
               COALESCE((SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.id), 0) AS chunk_count,
               COALESCE((SELECT COUNT(*) FROM obligations o WHERE o.document_id = d.id), 0) AS obligation_count
        FROM documents d
        WHERE d.id = :id
    """)
    row = session.execute(query, {"id": doc_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if isinstance(d["created_at"], datetime) else str(d["created_at"])
    d["sha256"] = d.get("sha256") or ""
    d["reference"] = d.get("reference") or ""
    return SourceDocument.model_validate(d)


def insert_document_sql(session: Session, doc: dict[str, Any]) -> None:
    query = text("""
        INSERT INTO documents (
            id, doc_type, title, reference, regulator, version_label, supersedes_id,
            is_synthetic, file_path, sha256, status, withdrawn_note, error, created_at
        ) VALUES (
            :id, :doc_type, :title, :reference, :regulator, :version_label, :supersedes_id,
            :is_synthetic, :file_path, :sha256, :status, :withdrawn_note, :error,
            COALESCE(:created_at, now())
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            status = EXCLUDED.status,
            version_label = EXCLUDED.version_label
    """)
    session.execute(query, doc)


# ---- Obligations -------------------------------------------------------------------------------

def list_obligations_sql(
    session: Session,
    document_id: str | None = None,
    applicability: str | None = None,
    review_status: str | None = None,
) -> list[Obligation]:
    clauses = []
    params: dict[str, Any] = {}
    if document_id:
        clauses.append("document_id = :doc_id")
        params["doc_id"] = document_id
    if applicability:
        clauses.append("applicability = :applicability")
        params["applicability"] = applicability
    if review_status:
        clauses.append("review_status = :review_status")
        params["review_status"] = review_status
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = text(f"SELECT * FROM obligations {where_sql} ORDER BY code ASC")
    rows = session.execute(query, params).mappings().all()
    return [Obligation.model_validate(dict(r)) for r in rows]


def get_obligation_sql(session: Session, obligation_id: str) -> Obligation | None:
    query = text("SELECT * FROM obligations WHERE id = :id")
    row = session.execute(query, {"id": obligation_id}).mappings().first()
    return Obligation.model_validate(dict(row)) if row else None


def update_obligation_sql(
    session: Session,
    obligation_id: str,
    review_status: str | None = None,
    fields: dict[str, Any] | None = None,
) -> Obligation | None:
    sets = []
    params: dict[str, Any] = {"id": obligation_id}
    if review_status is not None:
        sets.append("review_status = :review_status")
        params["review_status"] = review_status
    if fields:
        for k, v in fields.items():
            if k in ("action", "frequency", "deadline", "threshold", "condition"):
                sets.append(f"{k} = :{k}")
                params[k] = v

    if not sets:
        return get_obligation_sql(session, obligation_id)

    query = text(f"UPDATE obligations SET {', '.join(sets)} WHERE id = :id")
    session.execute(query, params)
    return get_obligation_sql(session, obligation_id)


# ---- Controls ----------------------------------------------------------------------------------

def list_controls_sql(session: Session) -> list[Control]:
    query = text("SELECT * FROM controls ORDER BY code ASC")
    rows = session.execute(query).mappings().all()
    return [Control.model_validate(dict(r)) for r in rows]


def get_control_sql(session: Session, control_id: str) -> Control | None:
    query = text("SELECT * FROM controls WHERE id = :id")
    row = session.execute(query, {"id": control_id}).mappings().first()
    return Control.model_validate(dict(row)) if row else None


# ---- Mappings ----------------------------------------------------------------------------------

def list_mappings_sql(session: Session, obligation_id: str | None = None) -> list[Mapping]:
    if obligation_id:
        query = text("SELECT * FROM mappings WHERE obligation_id = :ob_id ORDER BY id ASC")
        rows = session.execute(query, {"ob_id": obligation_id}).mappings().all()
    else:
        query = text("SELECT * FROM mappings ORDER BY id ASC")
        rows = session.execute(query).mappings().all()
    results: list[Mapping] = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("graph_path"), str):
            d["graph_path"] = json.loads(d["graph_path"])
        results.append(Mapping.model_validate(d))
    return results


def get_mapping_sql(session: Session, mapping_id: str) -> Mapping | None:
    query = text("SELECT * FROM mappings WHERE id = :id")
    row = session.execute(query, {"id": mapping_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("graph_path"), str):
        d["graph_path"] = json.loads(d["graph_path"])
    return Mapping.model_validate(d)


def update_mapping_status_sql(session: Session, mapping_id: str, status: str) -> Mapping | None:
    query = text("UPDATE mappings SET status = :status WHERE id = :id")
    session.execute(query, {"id": mapping_id, "status": status})
    return get_mapping_sql(session, mapping_id)


# ---- Gaps --------------------------------------------------------------------------------------

def list_gaps_sql(
    session: Session,
    status: str | None = None,
    priority: str | None = None,
) -> list[Gap]:
    clauses = []
    params: dict[str, Any] = {}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if priority:
        clauses.append("priority = :priority")
        params["priority"] = priority
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = text(f"SELECT * FROM gaps {where_sql} ORDER BY risk_score DESC")
    rows = session.execute(query, params).mappings().all()
    results: list[Gap] = []
    for r in rows:
        d = dict(r)
        d["risk_score"] = float(d["risk_score"])
        for col in ("control_ids", "evidence_ids", "risk_factors"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        results.append(Gap.model_validate(d))
    return results


def get_gap_sql(session: Session, gap_id: str) -> Gap | None:
    query = text("SELECT * FROM gaps WHERE id = :id")
    row = session.execute(query, {"id": gap_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["risk_score"] = float(d["risk_score"])
    for col in ("control_ids", "evidence_ids", "risk_factors"):
        if isinstance(d.get(col), str):
            d[col] = json.loads(d[col])
    return Gap.model_validate(d)


def update_gap_status_sql(
    session: Session,
    gap_id: str,
    status: str,
    reason: str | None = None,
) -> Gap | None:
    query = text("""
        UPDATE gaps
        SET status = :status, dismissed_reason = :reason
        WHERE id = :id
    """)
    session.execute(query, {"id": gap_id, "status": status, "reason": reason})
    return get_gap_sql(session, gap_id)


# ---- Remediations ------------------------------------------------------------------------------

def list_remediations_sql(session: Session) -> list[Remediation]:
    query = text("SELECT * FROM remediations ORDER BY created_at DESC")
    rows = session.execute(query).mappings().all()
    return [Remediation.model_validate(dict(r)) for r in rows]


def get_remediation_sql(session: Session, rem_id: str) -> Remediation | None:
    query = text("SELECT * FROM remediations WHERE id = :id")
    row = session.execute(query, {"id": rem_id}).mappings().first()
    return Remediation.model_validate(dict(row)) if row else None


def update_remediation_sql(
    session: Session,
    rem_id: str,
    status: str | None = None,
    action: str | None = None,
    owner_team: str | None = None,
) -> Remediation | None:
    sets = []
    params: dict[str, Any] = {"id": rem_id}
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if action is not None:
        sets.append("action = :action")
        params["action"] = action
    if owner_team is not None:
        sets.append("owner_team = :owner_team")
        params["owner_team"] = owner_team

    if sets:
        query = text(f"UPDATE remediations SET {', '.join(sets)} WHERE id = :id")
        session.execute(query, params)
    return get_remediation_sql(session, rem_id)


# ---- Evidence ----------------------------------------------------------------------------------

def list_evidence_sql(session: Session) -> list[Evidence]:
    query = text("SELECT * FROM evidence ORDER BY code ASC")
    rows = session.execute(query).mappings().all()
    results: list[Evidence] = []
    for r in rows:
        d = dict(r)
        for col in ("control_codes", "columns", "rows", "flagged_cells"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        results.append(Evidence.model_validate(d))
    return results


def get_evidence_sql(session: Session, evd_id: str) -> Evidence | None:
    query = text("SELECT * FROM evidence WHERE id = :id")
    row = session.execute(query, {"id": evd_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    for col in ("control_codes", "columns", "rows", "flagged_cells"):
        if isinstance(d.get(col), str):
            d[col] = json.loads(d[col])
    return Evidence.model_validate(d)


# ---- Audit Log ---------------------------------------------------------------------------------

def list_audit_sql(
    session: Session,
    entity_code: str | None = None,
    actor: str | None = None,
    limit: int = 100,
) -> list[AuditEntry]:
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if entity_code:
        clauses.append("(entity_code = :entity_code OR entity_code LIKE :entity_like)")
        params["entity_code"] = entity_code
        params["entity_like"] = f"{entity_code}%"
    if actor:
        clauses.append("actor = :actor")
        params["actor"] = actor
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    query = text(f"SELECT * FROM audit_log {where_sql} ORDER BY at DESC LIMIT :limit")
    rows = session.execute(query, params).mappings().all()
    results: list[AuditEntry] = []
    for r in rows:
        d = dict(r)
        d["at"] = d["at"].isoformat() if isinstance(d["at"], datetime) else str(d["at"])
        for col in ("before", "after"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        results.append(AuditEntry.model_validate(d))
    return results


# ---- Assessments -------------------------------------------------------------------------------

def get_assessment_for_obligation_sql(session: Session, obligation_id: str) -> Assessment | None:
    query = text("SELECT * FROM assessments WHERE obligation_id = :ob_id")
    row = session.execute(query, {"ob_id": obligation_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("evidence_ids"), str):
        d["evidence_ids"] = json.loads(d["evidence_ids"])
    return Assessment.model_validate(d)


# ---- Gap Trace (The Money Screen) --------------------------------------------------------------

def get_gap_trace_sql(session: Session, gap_id: str) -> GapTrace | None:
    gap = get_gap_sql(session, gap_id)
    if not gap:
        return None

    obligation = get_obligation_sql(session, gap.obligation_id)
    if not obligation:
        return None

    document = get_document_sql(session, obligation.document_id)
    if not document:
        return None

    mappings = list_mappings_sql(session, obligation_id=obligation.id)
    
    # Associated controls from gap control_ids + mappings
    control_id_set = set(gap.control_ids)
    for m in mappings:
        control_id_set.add(m.control_id)

    controls: list[Control] = []
    for cid in control_id_set:
        ctrl = get_control_sql(session, cid)
        if ctrl:
            controls.append(ctrl)

    assessment = get_assessment_for_obligation_sql(session, obligation.id)

    # Associated evidence
    evidence_id_set = set(gap.evidence_ids)
    if assessment and assessment.evidence_ids:
        evidence_id_set.update(assessment.evidence_ids)

    evidence_list: list[Evidence] = []
    for eid in evidence_id_set:
        evd = get_evidence_sql(session, eid)
        if evd:
            evidence_list.append(evd)

    # Remediations for this gap
    rem_query = text("SELECT * FROM remediations WHERE gap_id = :gap_id")
    rem_rows = session.execute(rem_query, {"gap_id": gap.id}).mappings().all()
    remediations = [Remediation.model_validate(dict(r)) for r in rem_rows]

    # Change if origin == 'change'
    change: RegulatoryChange | None = None
    if gap.change_id:
        chg_query = text("SELECT * FROM changes WHERE id = :cid")
        chg_row = session.execute(chg_query, {"cid": gap.change_id}).mappings().first()
        if chg_row:
            cd = dict(chg_row)
            for c in ("carried_over", "impact"):
                if isinstance(cd.get(c), str):
                    cd[c] = json.loads(cd[c])
            change = RegulatoryChange.model_validate(cd)

    # Audit log entries for this gap & obligation
    audit = list_audit_sql(session, entity_code=gap.code, limit=20)
    ob_audit = list_audit_sql(session, entity_code=obligation.code, limit=20)
    seen_audit_ids = {a.id for a in audit}
    for oa in ob_audit:
        if oa.id not in seen_audit_ids:
            audit.append(oa)
    audit.sort(key=lambda x: x.at, reverse=True)

    return GapTrace(
        gap=gap,
        obligation=obligation,
        document=document,
        controls=controls,
        mappings=mappings,
        assessment=assessment,
        evidence=evidence_list,
        remediations=remediations,
        change=change,
        audit=audit,
    )


# ---- Changes Comparison ------------------------------------------------------------------------

def get_change_comparison_sql(
    session: Session,
    old_doc_id: str = "doc-nsm-v1",
    new_doc_id: str = "doc-nsm-v2",
) -> ChangeComparisonResponse | None:
    old_doc = get_document_sql(session, old_doc_id)
    new_doc = get_document_sql(session, new_doc_id)
    if not old_doc or not new_doc:
        return None

    chg_query = text("""
        SELECT * FROM changes
        WHERE (old_document_id = :old_id AND new_document_id = :new_id)
           OR (old_document_id = :new_id AND new_document_id = :old_id)
        ORDER BY id ASC
    """)
    rows = session.execute(chg_query, {"old_id": old_doc_id, "new_id": new_doc_id}).mappings().all()
    changes: list[RegulatoryChange] = []
    for r in rows:
        d = dict(r)
        for col in ("carried_over", "impact"):
            if isinstance(d.get(col), str):
                d[col] = json.loads(d[col])
        changes.append(RegulatoryChange.model_validate(d))

    circ_query = text("""
        SELECT * FROM missing_circulars
        WHERE document_id = :doc_id
        ORDER BY row_num ASC
    """)
    circ_rows = session.execute(circ_query, {"doc_id": new_doc_id}).mappings().all()
    missing_circulars = [
        MissingCircular(
            row=r["row_num"],
            reference=r["reference"],
            date=r["circular_date"],
            subject=r["subject"],
        )
        for r in circ_rows
    ]

    return ChangeComparisonResponse(
        old_document=old_doc,
        new_document=new_doc,
        changes=changes,
        missing_circulars=missing_circulars,
    )


# ---- Dashboard Summary -------------------------------------------------------------------------

PHASE_OUT_DEADLINE = "2027-06-30T00:00:00+05:30"
GAP_TYPE_ORDER = ["design", "design_operating", "missing", "operating", "insufficient_info"]


def get_dashboard_summary_sql(session: Session) -> DashboardSummary:
    # 1. Obligations breakdown
    ob_stats = session.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE applicability = 'applicable') AS applicable,
            COUNT(*) FILTER (WHERE applicability != 'applicable') AS not_applicable,
            COUNT(*) FILTER (WHERE applicability = 'applicable' AND coverage = 'covered') AS cov_covered,
            COUNT(*) FILTER (WHERE applicability = 'applicable' AND coverage = 'partial') AS cov_partial,
            COUNT(*) FILTER (WHERE applicability = 'applicable' AND coverage = 'insufficient_info') AS cov_insufficient_info,
            COUNT(*) FILTER (WHERE applicability = 'applicable' AND coverage = 'none') AS cov_none,
            COUNT(*) FILTER (WHERE review_status = 'suggested') AS rev_suggested,
            COUNT(*) FILTER (WHERE review_status = 'accepted') AS rev_accepted,
            COUNT(*) FILTER (WHERE review_status = 'edited') AS rev_edited,
            COUNT(*) FILTER (WHERE review_status = 'rejected') AS rev_rejected,
            COUNT(*) FILTER (WHERE quote_verified = TRUE) AS quotes_verified
        FROM obligations
    """)).mappings().first()

    ob_total = ob_stats["total"] if ob_stats else 0
    ob_app = ob_stats["applicable"] if ob_stats else 0
    ob_not_app = ob_stats["not_applicable"] if ob_stats else 0

    coverage = {
        "covered": ob_stats["cov_covered"] if ob_stats else 0,
        "partial": ob_stats["cov_partial"] if ob_stats else 0,
        "insufficient_info": ob_stats["cov_insufficient_info"] if ob_stats else 0,
        "none": ob_stats["cov_none"] if ob_stats else 0,
    }

    # 2. Gaps breakdown
    gap_stats = session.execute(text("""
        SELECT
            COUNT(*) AS open_count,
            COALESCE(SUM(risk_score), 0) AS risk_exposure,
            COUNT(*) FILTER (WHERE priority = 'P1') AS p1,
            COUNT(*) FILTER (WHERE priority = 'P2') AS p2,
            COUNT(*) FILTER (WHERE priority = 'P3') AS p3
        FROM gaps
        WHERE status != 'dismissed'
    """)).mappings().first()

    open_gaps = gap_stats["open_count"] if gap_stats else 0
    risk_exposure = float(gap_stats["risk_exposure"]) if gap_stats else 0.0
    by_priority = {
        "P1": gap_stats["p1"] if gap_stats else 0,
        "P2": gap_stats["p2"] if gap_stats else 0,
        "P3": gap_stats["p3"] if gap_stats else 0,
    }

    # Gaps by type
    gap_type_rows = session.execute(text("""
        SELECT gap_type,
               COUNT(*) FILTER (WHERE priority = 'P1') AS p1,
               COUNT(*) FILTER (WHERE priority = 'P2') AS p2,
               COUNT(*) FILTER (WHERE priority = 'P3') AS p3
        FROM gaps
        WHERE status != 'dismissed'
        GROUP BY gap_type
    """)).mappings().all()

    type_counts_map = {r["gap_type"]: {"P1": r["p1"], "P2": r["p2"], "P3": r["p3"]} for r in gap_type_rows}
    gaps_by_type = []
    for gt in GAP_TYPE_ORDER:
        counts = type_counts_map.get(gt, {"P1": 0, "P2": 0, "P3": 0})
        if counts["P1"] + counts["P2"] + counts["P3"] > 0:
            gaps_by_type.append({"gap_type": gt, "counts": counts})

    # 3. Remediation stats
    rem_stats = session.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status IN ('approved', 'in_progress', 'completed', 'verified')) AS approved
        FROM remediations
    """)).mappings().first()
    rem_total = rem_stats["total"] if rem_stats else 0
    rem_approved = rem_stats["approved"] if rem_stats else 0

    # 4. Mappings review count & critic retries
    map_stats = session.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status IN ('suggested', 'needs_review')) AS to_review,
            COUNT(*) FILTER (WHERE critic = 'retried') AS retried
        FROM mappings
    """)).mappings().first()
    mappings_to_review = map_stats["to_review"] if map_stats else 0
    critic_retries = map_stats["retried"] if map_stats else 0

    # 5. Latest run
    last_run_row = session.execute(text("""
        SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT 1
    """)).mappings().first()
    last_run_at = ""
    llm_calls = 0
    if last_run_row:
        lr = dict(last_run_row)
        last_run_at = lr["started_at"].isoformat() if isinstance(lr["started_at"], datetime) else str(lr["started_at"])
        nodes = lr.get("nodes", [])
        if isinstance(nodes, str):
            nodes = json.loads(nodes)
        llm_calls = sum(n.get("llm_calls", 0) for n in nodes)

    # Calculate deadline days remaining
    now = datetime.now()
    deadline_dt = datetime.fromisoformat("2027-06-30T00:00:00+05:30")
    # Make naive for simple subtraction
    days_remaining = max(0, (deadline_dt.replace(tzinfo=None) - now).days)

    return DashboardSummary(
        obligations_total=ob_total,
        obligations_applicable=ob_app,
        obligations_not_applicable=ob_not_app,
        coverage=coverage,
        open_gaps=open_gaps,
        gaps_by_priority=by_priority,
        gaps_by_type=gaps_by_type,
        risk_exposure=risk_exposure,
        remediation_approved=rem_approved,
        remediation_total=rem_total,
        next_deadline={
            "label": "30 Jun 2027",
            "date": PHASE_OUT_DEADLINE,
            "days_remaining": days_remaining,
            "context": "NSM phase-out (N-07)",
        },
        review={
            "obligations_suggested": ob_stats["rev_suggested"] if ob_stats else 0,
            "obligations_accepted": ob_stats["rev_accepted"] if ob_stats else 0,
            "obligations_edited": ob_stats["rev_edited"] if ob_stats else 0,
            "obligations_rejected": ob_stats["rev_rejected"] if ob_stats else 0,
            "mappings_to_review": mappings_to_review,
            "quotes_verified": ob_stats["quotes_verified"] if ob_stats else 0,
            "quotes_total": ob_total,
        },
        critic_retries=critic_retries,
        llm_calls=llm_calls,
        last_run_at=last_run_at,
    )


# ---- Agent Runs --------------------------------------------------------------------------------

def list_runs_sql(session: Session) -> list[AgentRun]:
    query = text("SELECT * FROM agent_runs ORDER BY started_at DESC")
    rows = session.execute(query).mappings().all()
    results: list[AgentRun] = []
    for r in rows:
        d = dict(r)
        d["started_at"] = d["started_at"].isoformat() if isinstance(d["started_at"], datetime) else str(d["started_at"])
        if isinstance(d.get("nodes"), str):
            d["nodes"] = json.loads(d["nodes"])
        results.append(AgentRun.model_validate(d))
    return results


def get_run_sql(session: Session, run_id: str) -> AgentRun | None:
    query = text("SELECT * FROM agent_runs WHERE id = :id OR run_id = :id")
    row = session.execute(query, {"id": run_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    d["started_at"] = d["started_at"].isoformat() if isinstance(d["started_at"], datetime) else str(d["started_at"])
    if isinstance(d.get("nodes"), str):
        d["nodes"] = json.loads(d["nodes"])
    return AgentRun.model_validate(d)


# ---- Users & RBAC ------------------------------------------------------------------------------

def get_user_by_email_sql(session: Session, email: str) -> dict[str, Any] | None:
    query = text("SELECT * FROM users WHERE LOWER(email) = LOWER(:email) AND is_active = TRUE LIMIT 1")
    row = session.execute(query, {"email": email.strip()}).mappings().first()
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    if isinstance(d.get("last_login_at"), datetime):
        d["last_login_at"] = d["last_login_at"].isoformat()
    return d


def get_user_by_id_sql(session: Session, user_id: str) -> dict[str, Any] | None:
    query = text("SELECT * FROM users WHERE id = :id AND is_active = TRUE LIMIT 1")
    row = session.execute(query, {"id": user_id}).mappings().first()
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    if isinstance(d.get("last_login_at"), datetime):
        d["last_login_at"] = d["last_login_at"].isoformat()
    return d


def list_users_sql(session: Session) -> list[dict[str, Any]]:
    query = text("SELECT id, email, full_name, role, initials, is_active, created_at, last_login_at FROM users ORDER BY full_name ASC")
    rows = session.execute(query).mappings().all()
    results: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        if isinstance(d.get("last_login_at"), datetime):
            d["last_login_at"] = d["last_login_at"].isoformat()
        results.append(d)
    return results


def update_user_last_login_sql(session: Session, user_id: str) -> None:
    query = text("UPDATE users SET last_login_at = now() WHERE id = :id")
    session.execute(query, {"id": user_id})
    session.commit()

