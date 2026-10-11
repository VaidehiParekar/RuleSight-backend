from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.kg import kg_impact
from app.db.queries import get_change_comparison_sql
from app.db.session import get_session
from app.schemas.domain import ChangeComparisonResponse

router = APIRouter(prefix="/changes", tags=["changes"])


class CompareInput(BaseModel):
    old_document_id: str | None = "doc-nsm-v1"
    new_document_id: str | None = "doc-nsm-v2"


@router.get("/compare", response_model=ChangeComparisonResponse)
def compare_versions_get(
    old_id: str = "doc-nsm-v1",
    new_id: str = "doc-nsm-v2",
    session: Session = Depends(get_session),
) -> ChangeComparisonResponse:
    """Returns regulatory comparison between versions (e.g. NSM v1 and v2) and missing circular alerts."""
    res = get_change_comparison_sql(session, old_doc_id=old_id, new_doc_id=new_id)
    if not res:
        raise HTTPException(status_code=404, detail="Comparison documents not found")
    # Enrich changes with dynamic graph impact analysis
    for chg in res.changes:
        if chg.impact is None:
            chg.impact = {}
        chg.impact.setdefault("obligations", [])
        chg.impact.setdefault("controls", [])
        chg.impact.setdefault("gaps", [])
        affected = kg_impact(chg.clause_ref)
        if affected:
            chg.impact["graph_affected_entities"] = affected
    return res


@router.post("/compare", response_model=ChangeComparisonResponse)
def compare_versions_post(
    input_data: CompareInput,
    session: Session = Depends(get_session),
) -> ChangeComparisonResponse:
    """Returns regulatory comparison between versions (e.g. NSM v1 and v2) and missing circular alerts."""
    old_id = input_data.old_document_id or "doc-nsm-v1"
    new_id = input_data.new_document_id or "doc-nsm-v2"
    res = get_change_comparison_sql(session, old_doc_id=old_id, new_doc_id=new_id)
    if not res:
        raise HTTPException(status_code=404, detail="Comparison documents not found")
    # Enrich changes with dynamic graph impact analysis
    for chg in res.changes:
        if chg.impact is None:
            chg.impact = {}
        chg.impact.setdefault("obligations", [])
        chg.impact.setdefault("controls", [])
        chg.impact.setdefault("gaps", [])
        affected = kg_impact(chg.clause_ref)
        if affected:
            chg.impact["graph_affected_entities"] = affected
    return res


@router.get("/impact/{clause_ref}", response_model=list[str])
def get_clause_impact(clause_ref: str) -> list[str]:
    """Cascades changed clause through NetworkX knowledge graph to discover all affected obligations, controls, and gaps."""
    return kg_impact(clause_ref)
