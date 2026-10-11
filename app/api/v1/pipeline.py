"""Pipeline endpoints: start an AI run on uploaded RBI documents and follow its progress."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from app.core.actor import ActorInfo
from app.core.config import get_settings
from app.core.deps import get_current_actor, get_current_user, require_permission
from app.db.queries import get_run_sql, list_runs_sql
from app.db.session import get_session, write_transaction
from app.schemas.domain import AgentRun, UserResponse
from app.services.pipeline_runner import (
    PipelineBusyError,
    PipelineNotConfiguredError,
    RunRequest,
    build_provider,
    execute_run,
    start_run,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class RunBody(BaseModel):
    """Optional scope. An empty body analyses every regulation that has not been read yet."""

    document_id: str | None = Field(default=None, max_length=64)
    paragraphs: list[str] = Field(
        default_factory=list,
        max_length=200,
        description='Paragraph numbers to read, e.g. ["37", "38"]. Empty means all duties.',
    )


@router.get("/runs", response_model=list[AgentRun])
def list_runs(
    _user: UserResponse = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[AgentRun]:
    """Pipeline runs, newest first, with per-node timings, model calls and tokens."""
    return list_runs_sql(session)


@router.get("/runs/{id}", response_model=AgentRun)
def get_run(
    id: str,
    _user: UserResponse = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AgentRun:
    run = get_run_sql(session, id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.post("/run", response_model=AgentRun, status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline_run(
    request: Request,
    background: BackgroundTasks,
    body: RunBody | None = None,
    _user: UserResponse = Depends(require_permission("pipeline:run")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> AgentRun:
    """Starts a run and returns it at once with its nodes queued. Poll GET /runs/{id}."""
    settings = get_settings()
    try:
        # Fail fast, before a run is recorded, when no model is configured.
        build_provider(settings)
    except PipelineNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from None

    scope = body or RunBody()
    run_request = RunRequest(
        document_id=scope.document_id,
        paragraphs=frozenset(p.strip() for p in scope.paragraphs if p.strip()),
    )
    try:
        with write_transaction(session):
            run = start_run(session, settings, actor, run_request)
    except PipelineBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

    factory: sessionmaker[Session] = request.app.state.session_factory
    background.add_task(execute_run, factory, settings, run.id, actor, run_request)
    return run
