"""Cross-cutting infrastructure: configuration, logging, errors, middleware, security headers, knowledge graph, and deterministic rules."""

from app.core.kg import (
    get_graph,
    get_knowledge_graph_payload,
    kg_candidates,
    kg_impact,
    kg_orphans,
    rebuild_kg,
)
from app.core.rules import (
    calculate_risk,
    evaluate_gap_type,
    risk_rules,
)

__all__ = [
    "get_graph",
    "get_knowledge_graph_payload",
    "kg_candidates",
    "kg_impact",
    "kg_orphans",
    "rebuild_kg",
    "calculate_risk",
    "evaluate_gap_type",
    "risk_rules",
]
