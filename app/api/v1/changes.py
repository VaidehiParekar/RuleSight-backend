from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.kg import kg_impact, kg_impact_codes
from app.db.queries import get_change_comparison_sql, get_latest_superseding_pair_sql
from app.db.session import get_session
from app.schemas.domain import ChangeComparisonResponse, UserResponse

router = APIRouter(prefix="/changes", tags=["changes"])


class CompareInput(BaseModel):
    # Both omitted: compare the most recent document that supersedes another with its old version.
    old_document_id: str | None = None
    new_document_id: str | None = None


def _compare(session: Session, old_id: str | None, new_id: str | None) -> ChangeComparisonResponse:
    if not old_id or not new_id:
        pair = get_latest_superseding_pair_sql(session)
        if not pair:
            raise HTTPException(
                status_code=404,
                detail="No document supersedes another, so there is nothing to compare",
            )
        old_id, new_id = old_id or pair[0], new_id or pair[1]

    res = get_change_comparison_sql(session, old_doc_id=old_id, new_doc_id=new_id)
    if not res:
        raise HTTPException(status_code=404, detail="Comparison documents not found")
    # Add the obligations and gaps the knowledge graph links to each changed clause.
    for chg in res.changes:
        if not chg._clause_ref:
            continue
        affected = kg_impact_codes(chg._clause_ref)
        for code in affected["obligations"]:
            if code not in chg.impact.obligations:
                chg.impact.obligations.append(code)
        for code in affected["gaps"]:
            if code not in chg.impact.gaps:
                chg.impact.gaps.append(code)
    return res


@router.get("/compare", response_model=ChangeComparisonResponse)
def compare_versions_get(
    old_id: str | None = None,
    new_id: str | None = None,
    _user: UserResponse = Depends(require_permission("changes:compare")),
    session: Session = Depends(get_session),
) -> ChangeComparisonResponse:
    """Returns the regulatory comparison between two document versions and missing circulars."""
    return _compare(session, old_id, new_id)


@router.post("/compare", response_model=ChangeComparisonResponse)
def compare_versions_post(
    input_data: CompareInput,
    _user: UserResponse = Depends(require_permission("changes:compare")),
    session: Session = Depends(get_session),
) -> ChangeComparisonResponse:
    """Returns the regulatory comparison between two document versions and missing circulars."""
    return _compare(session, input_data.old_document_id, input_data.new_document_id)


@router.get("/impact/{clause_ref}", response_model=list[str])
def get_clause_impact(
    clause_ref: str,
    _user: UserResponse = Depends(require_permission("changes:read")),
) -> list[str]:
    """IDs of the obligations and gaps the knowledge graph links to a changed clause."""
    return kg_impact(clause_ref)
