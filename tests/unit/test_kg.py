"""Unit tests for NetworkX in-memory Knowledge Graph (app.core.kg)."""

from app.core.kg import (
    get_graph,
    get_knowledge_graph_payload,
    kg_candidates,
    kg_impact,
    kg_orphans,
)


def test_kg_graph_structure() -> None:
    g = get_graph()
    g.clear()

    # Add mock nodes
    g.add_node("clause:ob-1", type="clause", label="Section 23", detail="MD")
    g.add_node("ob-1", type="obligation", label="OB-01", detail="Customer CDD")
    g.add_edge("ob-1", "clause:ob-1", type="DERIVED_FROM")

    g.add_node("topic:cdd", type="topic", label="cdd", detail="Topic")
    g.add_edge("ob-1", "topic:cdd", type="ABOUT")

    g.add_node("ctrl-1", type="control", label="CTL-01", detail="KYC check")
    g.add_edge("ctrl-1", "topic:cdd", type="ABOUT")

    g.add_node("gap-1", type="gap", label="GAP-01", detail="CDD mismatch")
    g.add_edge("gap-1", "ob-1", type="ON")

    # Test kg_candidates
    candidates = kg_candidates("ob-1")
    assert len(candidates) == 1
    assert candidates[0]["control_id"] == "ctrl-1"
    assert candidates[0]["control_code"] == "CTL-01"

    # Test kg_impact
    impacted = kg_impact("Section 23")
    assert "ob-1" in impacted
    assert "gap-1" in impacted

    # Test kg_orphans
    # ob-1 does not have a COVERED_BY edge yet
    assert "ob-1" in kg_orphans()

    # Add coverage edge
    g.add_edge("ob-1", "ctrl-1", type="COVERED_BY", coverage="covered", status="accepted")
    assert "ob-1" not in kg_orphans()

    # Test payload generation
    payload = get_knowledge_graph_payload()
    node_ids = {n.id for n in payload.nodes}
    assert "clause:ob-1" in node_ids
    assert "ob-1" in node_ids
    assert "ctrl-1" in node_ids
    assert "gap-1" in node_ids
