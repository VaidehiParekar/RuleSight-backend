from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.deps import get_current_actor, require_permission
from app.core.kg import kg_candidates
from app.db.queries import (
    get_control_sql,
    get_mapping_sql,
    get_obligation_sql,
    list_mappings_sql,
    update_mapping_status_sql,
)
from app.db.session import get_session, write_transaction
from app.schemas.domain import Mapping, MappingStatus, UserResponse

router = APIRouter(prefix="/mappings", tags=["mappings"])


class MappingUpdateInput(BaseModel):
    status: MappingStatus


@router.get("", response_model=list[Mapping])
def list_mappings(
    obligation_id: str | None = Query(None),
    _user: UserResponse = Depends(require_permission("mappings:read")),
    session: Session = Depends(get_session),
) -> list[Mapping]:
    """Lists obligation-to-control mappings with graph paths and critic results."""
    mappings = list_mappings_sql(session, obligation_id=obligation_id)
    # Enrich any mapping lacking a graph_path using the knowledge graph candidates
    for m in mappings:
        if not m.graph_path:
            candidates = kg_candidates(m.obligation_id)
            for c in candidates:
                if c.get("control_id") == m.control_id and c.get("path"):
                    m.graph_path = c["path"]
                    break
    return mappings


@router.get("/candidates/{obligation_id}", response_model=list[dict[str, Any]])
def get_mapping_candidates(
    obligation_id: str,
    _user: UserResponse = Depends(require_permission("mappings:read")),
) -> list[dict[str, Any]]:
    """Candidate controls that share a regulatory topic with the obligation (knowledge graph)."""
    return kg_candidates(obligation_id)


@router.get("/{id}", response_model=Mapping)
def get_mapping(
    id: str,
    _user: UserResponse = Depends(require_permission("mappings:read")),
    session: Session = Depends(get_session),
) -> Mapping:
    mapping = get_mapping_sql(session, id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    if not mapping.graph_path:
        candidates = kg_candidates(mapping.obligation_id)
        for c in candidates:
            if c.get("control_id") == mapping.control_id and c.get("path"):
                mapping.graph_path = c["path"]
                break
    return mapping


@router.patch("/{id}", response_model=Mapping)
def update_mapping(
    id: str,
    input_data: MappingUpdateInput,
    _user: UserResponse = Depends(require_permission("mappings:verify")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> Mapping:
    """Updates a mapping status (e.g. accepted/rejected) and records an audit log entry."""
    with write_transaction(session):
        before_mapping = get_mapping_sql(session, id)
        if not before_mapping:
            raise HTTPException(status_code=404, detail="Mapping not found")

        updated = update_mapping_status_sql(session, id, input_data.status)
        if not updated:
            raise HTTPException(status_code=404, detail="Failed to update mapping")

        obligation = get_obligation_sql(session, updated.obligation_id)
        control = get_control_sql(session, updated.control_id)
        ob_code = obligation.code if obligation else ""
        entity_code = f"{ob_code} -> {control.code if control else ''}"

        record_audit(
            session,
            actor=actor,
            action=f"Updated mapping to {input_data.status}",
            entity_type="mapping",
            entity_code=entity_code,
            before={"status": before_mapping.status},
            after={"status": updated.status},
        )

    return updated
