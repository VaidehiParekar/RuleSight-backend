from fastapi import APIRouter

from app.core.errors import ServiceUnavailableError
from app.db.session import DbSession
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.services.health_service import is_database_reachable

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=LivenessResponse, summary="Liveness probe")
def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"description": "A required dependency is unavailable"}},
)
def readiness(session: DbSession) -> ReadinessResponse:
    if not is_database_reachable(session):
        raise ServiceUnavailableError("The database is unavailable.")
    return ReadinessResponse(status="ready", database="ok")
