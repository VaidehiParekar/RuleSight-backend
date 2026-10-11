from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.queries import get_dashboard_summary_sql
from app.db.session import get_session
from app.schemas.domain import DashboardSummary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(session: Session = Depends(get_session)) -> DashboardSummary:
    """Returns aggregated compliance metrics, exposure, and review queue counts."""
    return get_dashboard_summary_sql(session)
