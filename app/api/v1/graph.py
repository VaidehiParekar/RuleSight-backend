from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.kg import get_knowledge_graph_payload, kg_orphans, rebuild_kg
from app.db.session import get_session
from app.schemas.domain import KnowledgeGraph

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=KnowledgeGraph)
def get_graph(
    focus: str | None = Query(None),
    session: Session = Depends(get_session),
) -> KnowledgeGraph:
    """Returns nodes and edges from the in-memory NetworkX knowledge graph."""
    payload = get_knowledge_graph_payload()
    if not payload.nodes:
        rebuild_kg(session)
        payload = get_knowledge_graph_payload()
    return payload


@router.post("/rebuild", response_model=KnowledgeGraph)
def rebuild_graph(session: Session = Depends(get_session)) -> KnowledgeGraph:
    """Explicitly reloads all entities from PostgreSQL and rebuilds the NetworkX graph."""
    rebuild_kg(session)
    return get_knowledge_graph_payload()


@router.get("/orphans", response_model=list[str])
def get_uncovered_obligations() -> list[str]:
    """Returns IDs of obligations that have no COVERED_BY edge in the graph."""
    return kg_orphans()
