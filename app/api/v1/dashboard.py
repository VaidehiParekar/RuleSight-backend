from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.queries import get_dashboard_summary_sql
from app.db.session import get_session
from app.schemas.domain import DashboardSummary, UserResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    # The summary aggregates obligations, gaps and remediations; every role that can read
    # obligations may see it.
    _user: UserResponse = Depends(require_permission("obligations:read")),
    session: Session = Depends(get_session),
) -> DashboardSummary:
    """Returns aggregated compliance metrics, exposure, and review queue counts."""
    return get_dashboard_summary_sql(session)
