"""In-memory Knowledge Graph service using NetworkX.

Built from PostgreSQL via raw SQL queries at startup and refreshed after pipeline runs.
PostgreSQL remains the sole source of truth.
"""

from typing import Any

import networkx as nx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.domain import GraphEdge, GraphNode, KnowledgeGraph

# Singleton in-memory graph
_graph = nx.MultiDiGraph()


def rebuild_kg(session: Session) -> None:
    """Reloads all entities from PostgreSQL via raw SQL and rebuilds the NetworkX graph."""
    global _graph
    g = nx.MultiDiGraph()

    # 1. Obligations and Clauses
    ob_rows = (
        session.execute(
            text("SELECT id, code, clause_ref, source_label, summary, topic FROM obligations")
        )
        .mappings()
        .all()
    )

    for r in ob_rows:
        ob_id = r["id"]
        clause_id = f"clause:{ob_id}"

        # Clause node
        g.add_node(clause_id, type="clause", label=r["clause_ref"], detail=r["source_label"])
        # Obligation node
        g.add_node(ob_id, type="obligation", label=r["code"], detail=r["summary"])
        # Edge
        g.add_edge(ob_id, clause_id, type="DERIVED_FROM")

        # Topic node & edge
        if r["topic"]:
            topic_id = f"topic:{r['topic']}"
            g.add_node(topic_id, type="topic", label=r["topic"], detail="Regulatory topic")
            g.add_edge(ob_id, topic_id, type="ABOUT")

    # 2. Controls
    ctrl_rows = (
        session.execute(text("SELECT id, code, name, owner, topic FROM controls")).mappings().all()
    )

    for r in ctrl_rows:
        ctrl_id = r["id"]
        g.add_node(ctrl_id, type="control", label=r["code"], detail=r["name"])
        if r["topic"]:
            topic_id = f"topic:{r['topic']}"
            g.add_node(topic_id, type="topic", label=r["topic"], detail="Regulatory topic")
            g.add_edge(ctrl_id, topic_id, type="ABOUT")

    # 3. Evidence
    evd_rows = (
        session.execute(text("SELECT id, code, title, control_codes FROM evidence"))
        .mappings()
        .all()
    )

    code_to_ctrl_id = {r["code"]: r["id"] for r in ctrl_rows}

    for r in evd_rows:
        evd_id = r["id"]
        g.add_node(evd_id, type="evidence", label=r["code"], detail=r["title"])
        control_codes = r["control_codes"] if isinstance(r["control_codes"], list) else []
        for c_code in control_codes:
            if c_code in code_to_ctrl_id:
                g.add_edge(code_to_ctrl_id[c_code], evd_id, type="SUPPORTED_BY")

    # 4. Mappings
    map_rows = (
        session.execute(text("SELECT obligation_id, control_id, coverage, status FROM mappings"))
        .mappings()
        .all()
    )

    for r in map_rows:
        if g.has_node(r["obligation_id"]) and g.has_node(r["control_id"]):
            g.add_edge(
                r["obligation_id"],
                r["control_id"],
                type="COVERED_BY",
                coverage=r["coverage"],
                status=r["status"],
            )

    # 5. Gaps
    gap_rows = (
        session.execute(
            text("SELECT id, code, obligation_id, title, control_ids, evidence_ids FROM gaps")
        )
        .mappings()
        .all()
    )

    for r in gap_rows:
        gap_id = r["id"]
        g.add_node(gap_id, type="gap", label=r["code"], detail=r["title"])
        if g.has_node(r["obligation_id"]):
            g.add_edge(gap_id, r["obligation_id"], type="ON")

        ctrl_ids = r["control_ids"] if isinstance(r["control_ids"], list) else []
        for cid in ctrl_ids:
            if g.has_node(cid):
                g.add_edge(gap_id, cid, type="INVOLVES")

        evd_ids = r["evidence_ids"] if isinstance(r["evidence_ids"], list) else []
        for eid in evd_ids:
            if g.has_node(eid):
                g.add_edge(gap_id, eid, type="EVIDENCED_BY")

    # 6. Remediations
    rem_rows = session.execute(text("SELECT id, gap_id, action FROM remediations")).mappings().all()

    for r in rem_rows:
        rem_id = r["id"]
        g.add_node(
            rem_id, type="remediation", label=f"Fix {r['gap_id'].upper()}", detail=r["action"]
        )
        if g.has_node(r["gap_id"]):
            g.add_edge(r["gap_id"], rem_id, type="REMEDIATED_BY")

    _graph = g


def get_graph() -> nx.MultiDiGraph:
    return _graph


def kg_candidates(obligation_id: str) -> list[dict[str, Any]]:
    """Finds controls that share a topic or owner with the obligation."""
    candidates: list[dict[str, Any]] = []
    if not _graph.has_node(obligation_id):
        return candidates

    # Find topics linked to obligation
    topics = [
        target
        for _, target, data in _graph.out_edges(obligation_id, data=True)
        if data.get("type") == "ABOUT"
    ]

    for topic in topics:
        # Find controls linked to this topic
        for src, _, data in _graph.in_edges(topic, data=True):
            if data.get("type") == "ABOUT" and _graph.nodes[src].get("type") == "control":
                candidates.append(
                    {
                        "control_id": src,
                        "control_code": _graph.nodes[src].get("label"),
                        "path": [obligation_id, topic, src],
                    }
                )

    return candidates


def kg_impact(clause_ref: str) -> list[str]:
    """Finds all obligations, controls, and gaps affected when a clause changes."""
    affected = []
    for node, data in _graph.nodes(data=True):
        if data.get("type") == "clause" and data.get("label") == clause_ref:
            # Incoming DERIVED_FROM edges from obligations
            for ob_id, _, edge_data in _graph.in_edges(node, data=True):
                if edge_data.get("type") == "DERIVED_FROM":
                    affected.append(ob_id)
                    # Downstream gaps
                    for gap_id, _, gap_edge in _graph.in_edges(ob_id, data=True):
                        if gap_edge.get("type") == "ON":
                            affected.append(gap_id)
    return affected


def kg_impact_codes(clause_ref: str) -> dict[str, list[str]]:
    """Codes of the obligations and gaps affected by a clause change, grouped by node type."""
    grouped: dict[str, list[str]] = {"obligations": [], "gaps": []}
    for node_id in kg_impact(clause_ref):
        data = _graph.nodes[node_id]
        key = f"{data.get('type')}s"
        label = data.get("label", node_id)
        if key in grouped and label not in grouped[key]:
            grouped[key].append(label)
    return grouped


def kg_orphans() -> list[str]:
    """Returns obligations with no COVERED_BY edge."""
    orphans = []
    for node, data in _graph.nodes(data=True):
        if data.get("type") == "obligation":
            has_coverage = any(
                edge_data.get("type") == "COVERED_BY"
                for _, _, edge_data in _graph.out_edges(node, data=True)
            )
            if not has_coverage:
                orphans.append(node)
    return orphans


def get_knowledge_graph_payload() -> KnowledgeGraph:
    """Formats the current graph into KnowledgeGraph Pydantic schema for the frontend."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    for node_id, data in _graph.nodes(data=True):
        node_type = data.get("type", "unknown")
        # Exclude synthetic topic nodes from raw display if not expected by frontend COLUMNS
        if node_type in ("clause", "obligation", "control", "evidence", "gap", "remediation"):
            nodes.append(
                GraphNode(
                    id=node_id,
                    type=node_type,
                    label=data.get("label", node_id),
                    detail=data.get("detail", ""),
                )
            )

    for src, tgt, data in _graph.edges(data=True):
        edge_type = data.get("type", "")
        # Only include edges between visible display nodes
        if _graph.has_node(src) and _graph.has_node(tgt):
            src_type = _graph.nodes[src].get("type")
            tgt_type = _graph.nodes[tgt].get("type")
            if src_type != "topic" and tgt_type != "topic":
                edges.append(
                    GraphEdge(
                        source=src,
                        target=tgt,
                        type=edge_type,
                    )
                )

    return KnowledgeGraph(nodes=nodes, edges=edges)
