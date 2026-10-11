import logging

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.deps import require_permission
from app.schemas.domain import EvalReport, UserResponse

router = APIRouter(prefix="/eval", tags=["evaluation"])
logger = logging.getLogger("app.eval")


@router.get("/latest", response_model=EvalReport)
def get_latest_eval(
    _user: UserResponse = Depends(require_permission("eval:read")),
) -> EvalReport:
    """Returns the latest measured evaluation report (EVAL_REPORT_PATH), never invented numbers.

    Without a report file the response says so (is_mock=true, no metrics) instead of guessing.
    """
    path = get_settings().eval_report_path
    if path is not None and path.is_file():
        try:
            return EvalReport.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError):
            logger.exception("The evaluation report at EVAL_REPORT_PATH could not be read")
    return EvalReport(
        is_mock=True,
        scored_at=None,
        method="No measured evaluation report is available yet.",
        metrics=[],
    )
