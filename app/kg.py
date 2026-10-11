"""Re-export from app.core.kg for backward compatibility."""

from app.core.kg import (
    _graph,
    get_graph,
    get_knowledge_graph_payload,
    kg_candidates,
    kg_impact,
    kg_orphans,
    rebuild_kg,
)

__all__ = [
    "_graph",
    "get_graph",
    "get_knowledge_graph_payload",
    "kg_candidates",
    "kg_impact",
    "kg_orphans",
    "rebuild_kg",
]
