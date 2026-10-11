"""Runs the AI pipeline on uploaded RBI documents and stores what it finds.

A run is recorded first (status "running") so the UI can show it at once; the model calls then
happen in the background. Each regulation document is read paragraph by paragraph, passed through
extract -> map -> classify gaps -> draft remediation, and the results are written in one
transaction per document. Nothing is final: obligations, mappings and gaps are stored as
suggestions for a person to review, and anything the critic could not verify is marked for review.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.actor import ActorInfo, record_audit
from app.core.config import Settings
from app.core.kg import rebuild_kg
from app.core.rules import calculate_risk, evaluate_gap_type
from app.integrations.llm.base import LLMProviderError, StructuredLLMProvider, usage_of
from app.integrations.llm.gemini import build_gemini_provider
from app.schemas.domain import AgentRun, Applicability, Coverage, DesignAssessment
from app.services.change_runner import CHANGE_NODE, run_change_branch
from app.services.evaluation import run_evaluation
from app.services.regulation_text import (
    Paragraph,
    batch_by_size,
    extract_text,
    select_paragraphs,
    split_paragraphs,
)
from app.workflows.critic import Verdict
from app.workflows.pipeline import AgentRun as NodeRecord
from app.workflows.pipeline import PipelineResult, run_pipeline
from app.workflows.schemas import NOT_SPECIFIED, RemediationDraft
from app.workflows.steps import (
    ClauseInput,
    ControlInput,
    GapInput,
    MappingResult,
    ObligationInput,
    draft_remediation,
    keyword_candidates,
)

logger = logging.getLogger(__name__)

NODES = ("extract_obligations", "map_controls", "draft_remediation")
# Conditional branch: listed only when a document in the run supersedes another.
CONDITIONAL_NODES = (CHANGE_NODE,)

# Strongest coverage first: an obligation is as covered as its best control.
_COVERAGE_RANK: dict[str, int] = {"covered": 3, "partial": 2, "insufficient_info": 1, "none": 0}

_GAP_LABEL = {
    "missing": "no control in place",
    "design": "control design falls short",
    "operating": "control not operating as designed",
    "design_operating": "control design and operation fall short",
    "insufficient_info": "not enough information to confirm",
}


class PipelineBusyError(Exception):
    """Another run is still in progress."""


class PipelineNotConfiguredError(Exception):
    """No language model is configured, so a run cannot start."""


@dataclass(frozen=True)
class RunRequest:
    """What to analyse. Without a document, every regulation not yet analysed is read."""

    document_id: str | None = None
    paragraphs: frozenset[str] = frozenset()


@dataclass
class _Totals:
    """Per-node totals across all documents in one run."""

    records: dict[str, list[NodeRecord]] = field(default_factory=dict)
    notes: dict[str, list[str]] = field(default_factory=dict)

    def record(self, record: NodeRecord, note: str) -> None:
        self.records.setdefault(record.node, []).append(record)
        self.notes.setdefault(record.node, []).append(note)

    def add(self, result: PipelineResult, label: str) -> None:
        for record in result.runs:
            self.records.setdefault(record.node, []).append(record)
        extracted = [o for o in result.obligations if o.draft is not None]
        verified = [o for o in extracted if o.verdict == Verdict.ACCEPTED]
        flagged_maps = [m for m in result.mappings if m.verdict != Verdict.ACCEPTED]
        self.notes.setdefault("extract_obligations", []).append(
            f"{label}: {len(extracted)} obligations, {len(verified)} quotes verified"
        )
        self.notes.setdefault("map_controls", []).append(
            f"{label}: {len(result.mappings)} mappings ({len(flagged_maps)} need review), "
            f"{len(result.gaps)} gaps"
        )
        self.notes.setdefault("draft_remediation", []).append(
            f"{label}: {sum(1 for r in result.remediations if r.draft)} remediation drafts"
        )


# ---------------------------------------------------------------- provider


def build_provider(settings: Settings) -> StructuredLLMProvider:
    if settings.llm_provider != "gemini" or settings.gemini_api_key is None:
        raise PipelineNotConfiguredError(
            "Set LLM_PROVIDER=gemini and GEMINI_API_KEY in the backend .env to run the pipeline."
        )
    return build_gemini_provider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=cast("str", settings.llm_model),
        cache_dir=settings.llm_cache_dir,
        transport_attempts=settings.llm_transport_attempts,
        backoff_seconds=settings.llm_retry_backoff_seconds,
        timeout_seconds=settings.llm_timeout_seconds,
        min_interval_seconds=settings.llm_min_interval_seconds,
    )


# ---------------------------------------------------------------- start


def _iso(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def _row_to_run(row: Any) -> AgentRun:
    data = dict(row)
    data["started_at"] = _iso(data["started_at"])
    if isinstance(data.get("nodes"), str):
        data["nodes"] = json.loads(data["nodes"])
    return AgentRun.model_validate(data)


def start_run(
    session: Session, settings: Settings, actor: ActorInfo, request: RunRequest
) -> AgentRun:
    """Records a run with every node queued. The caller commits, then schedules ``execute_run``."""
    busy = session.execute(
        text("""
            SELECT 1 FROM agent_runs
            WHERE status IN ('queued', 'running')
              AND started_at > now() - make_interval(mins => :timeout)
            LIMIT 1
        """),
        {"timeout": settings.pipeline_run_timeout_minutes},
    ).first()
    if busy:
        raise PipelineBusyError("A pipeline run is already in progress.")

    run_hex = uuid.uuid4().hex[:6]
    queued = [
        {
            "node": node,
            "status": "queued",
            "offset_ms": 0,
            "duration_ms": 0,
            "llm_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "note": None,
            "conditional": node in CONDITIONAL_NODES,
        }
        for node in _run_nodes(_expects_change(session, request))
    ]
    scope = f"document {request.document_id}" if request.document_id else "new regulations"
    row = (
        session.execute(
            text("""
                INSERT INTO agent_runs (id, run_id, started_at, trigger, cache_hits, status, nodes)
                VALUES (:id, :run_id, now(), :trigger, 0, 'running', CAST(:nodes AS jsonb))
                RETURNING *
            """),
            {
                "id": f"run-{run_hex}",
                "run_id": run_hex,
                "trigger": f"{actor.name} ran the pipeline on {scope}"[:128],
                "nodes": json.dumps(queued),
            },
        )
        .mappings()
        .one()
    )
    record_audit(
        session,
        actor=actor,
        action="Started pipeline run",
        entity_type="pipeline",
        entity_code=f"run-{run_hex}",
        after={"scope": scope, "paragraphs": sorted(request.paragraphs) or None},
    )
    return _row_to_run(row)


def _run_nodes(with_change: bool) -> tuple[str, ...]:
    return NODES + CONDITIONAL_NODES if with_change else NODES


def _expects_change(session: Session, request: RunRequest) -> bool:
    """True when a document this run will read supersedes another (the change branch runs)."""
    if request.document_id:
        row = session.execute(
            text("""
                SELECT 1 FROM documents
                WHERE id = :id AND doc_type = 'regulation' AND supersedes_id IS NOT NULL
            """),
            {"id": request.document_id},
        ).first()
    else:
        row = session.execute(
            text("""
                SELECT 1 FROM documents d
                WHERE d.doc_type = 'regulation' AND d.status <> 'superseded'
                  AND d.supersedes_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM obligations o WHERE o.document_id = d.id)
                LIMIT 1
            """)
        ).first()
    return row is not None


# ---------------------------------------------------------------- inputs


@dataclass(frozen=True)
class _Document:
    id: str
    title: str
    regulator: str | None
    file_path: str | None
    supersedes_id: str | None = None


def _documents(session: Session, request: RunRequest) -> list[_Document]:
    if request.document_id:
        rows = session.execute(
            text("""
                SELECT id, title, regulator, file_path, supersedes_id FROM documents
                WHERE id = :id AND doc_type = 'regulation'
            """),
            {"id": request.document_id},
        )
    else:
        rows = session.execute(
            text("""
                SELECT d.id, d.title, d.regulator, d.file_path, d.supersedes_id
                FROM documents d
                WHERE d.doc_type = 'regulation' AND d.status <> 'superseded'
                  AND NOT EXISTS (SELECT 1 FROM obligations o WHERE o.document_id = d.id)
                ORDER BY d.created_at
            """)
        )
    return [_Document(**dict(r)) for r in rows.mappings()]


def _paragraphs(session: Session, document: _Document) -> list[Paragraph]:
    """Paragraphs from the stored file; falls back to the chunks saved at upload."""
    if document.file_path and Path(document.file_path).is_file():
        content = Path(document.file_path).read_bytes()
        paragraphs = split_paragraphs(extract_text(content, document.file_path))
        if paragraphs:
            _replace_chunks(session, document.id, paragraphs)
            return paragraphs
    rows = session.execute(
        text("SELECT clause_ref, text FROM chunks WHERE document_id = :id ORDER BY created_at"),
        {"id": document.id},
    ).mappings()
    return [Paragraph(ref=r["clause_ref"], text=r["text"]) for r in rows]


def _replace_chunks(session: Session, document_id: str, paragraphs: Sequence[Paragraph]) -> None:
    """Stores the parsed paragraphs as the document's chunks (PDF text is only readable here)."""
    session.execute(text("DELETE FROM chunks WHERE document_id = :id"), {"id": document_id})
    for index, paragraph in enumerate(paragraphs, start=1):
        session.execute(
            text("""
                INSERT INTO chunks (id, document_id, clause_ref, page, text)
                VALUES (:id, :document_id, :clause_ref, NULL, :text)
            """),
            {
                "id": f"chk-{document_id}-{index}",
                "document_id": document_id,
                "clause_ref": paragraph.ref,
                "text": paragraph.text,
            },
        )


def _already_read(session: Session, document_id: str) -> set[str]:
    rows = session.execute(
        text("SELECT DISTINCT clause_ref FROM obligations WHERE document_id = :id"),
        {"id": document_id},
    )
    return {r[0] for r in rows}


@dataclass(frozen=True)
class _Control:
    id: str
    code: str
    name: str


def _controls(session: Session) -> tuple[list[ControlInput], dict[str, _Control]]:
    rows = session.execute(
        text("SELECT id, code, name, description, source_quote FROM controls ORDER BY code")
    ).mappings()
    inputs: list[ControlInput] = []
    by_code: dict[str, _Control] = {}
    for r in rows:
        body = r["description"] + (
            f" Policy text: {r['source_quote']}" if r["source_quote"] else ""
        )
        inputs.append(ControlInput(code=r["code"], name=r["name"], text=body))
        by_code[r["code"]] = _Control(id=r["id"], code=r["code"], name=r["name"])
    return inputs, by_code


# ---------------------------------------------------------------- gaps (deterministic)


def _coverage_by_obligation(mappings: Sequence[MappingResult]) -> dict[str, list[MappingResult]]:
    grouped: dict[str, list[MappingResult]] = {}
    for mapping in mappings:
        if mapping.judgement is not None:
            grouped.setdefault(mapping.obligation_code, []).append(mapping)
    return grouped


def _relevant(judged: Sequence[MappingResult]) -> list[MappingResult]:
    """Controls that at least partly address the duty; unrelated controls say nothing about it."""
    return [m for m in judged if m.judgement and m.judgement.coverage in ("covered", "partial")]


def _design(judged: Sequence[MappingResult]) -> DesignAssessment:
    designs = {m.judgement.design for m in judged if m.judgement}
    if "inadequate" in designs:
        return "inadequate"
    return "adequate" if "adequate" in designs else "unknown"


def make_gap_builder(
    controls: dict[str, _Control],
) -> Callable[[Sequence[ObligationInput], Sequence[MappingResult]], list[GapInput]]:
    """Applies the rule tree in app.core.rules to this run's judgements."""

    def build(
        obligations: Sequence[ObligationInput], mappings: Sequence[MappingResult]
    ) -> list[GapInput]:
        judged = _coverage_by_obligation(mappings)
        gaps: list[GapInput] = []
        for obligation in obligations:
            own = judged.get(obligation.code, [])
            coverages = [cast("Coverage", m.judgement.coverage) for m in own if m.judgement]
            gap_type = evaluate_gap_type(
                cast("Applicability", obligation.applicability), coverages, _design(_relevant(own))
            )
            if gap_type is None:
                continue
            related = _relevant(own)
            reasons = [m.judgement.rationale for m in related if m.judgement]
            gaps.append(
                GapInput(
                    code=f"GAP-{len(gaps) + 1:03d}",
                    obligation_code=obligation.code,
                    gap_type=gap_type,
                    description=" ".join(reasons) or "No existing control addresses this duty.",
                    control_names=tuple(
                        controls[m.control_code].name for m in related if m.control_code in controls
                    ),
                )
            )
        return gaps

    return build


# ---------------------------------------------------------------- persistence


def _specified(value: str) -> str | None:
    return None if not value or value.strip() == NOT_SPECIFIED else value


def _next_number(session: Session, table: str, prefix: str) -> int:
    """Next free number for codes like OB-12 or G-08, so new rows never collide with old ones."""
    row = session.execute(
        text(
            f"SELECT COALESCE(MAX(CAST(SUBSTRING(code FROM :pattern) AS INTEGER)), 0) FROM {table}"  # noqa: S608 - table is a module constant
        ),
        {"pattern": f"^{prefix}-([0-9]+)$"},
    ).scalar_one()
    return int(row) + 1


def _persist(
    session: Session,
    document: _Document,
    result: PipelineResult,
    controls: dict[str, _Control],
) -> dict[str, int]:
    source_label = f"{document.regulator or 'Regulator'} · {document.title}"[:128]
    judged = _coverage_by_obligation(result.mappings)
    gap_by_obligation = {g.obligation_code: g for g in result.gaps}

    obligation_ids: dict[str, str] = {}
    # Codes the model saw during this run, mapped to the codes people see in the app.
    renames: dict[str, str] = {}
    obligation_topics: dict[str, str] = {}
    next_ob = _next_number(session, "obligations", "OB")
    for index, settled in enumerate(result.obligations, start=1):
        draft = settled.draft
        if draft is None:
            continue
        pipeline_code = f"OB-{index:03d}"
        own = judged.get(pipeline_code, [])
        best = max(
            (m.judgement.coverage for m in own if m.judgement),
            key=lambda c: _COVERAGE_RANK[c],
            default="none",
        )
        coverage = "not_applicable" if draft.applicability == "not_applicable" else best
        _, _, factors = calculate_risk(topic=f"{draft.topic} {document.title}", gap_type="missing")
        obligation_id = f"ob-{uuid.uuid4().hex[:10]}"
        session.execute(
            text("""
                INSERT INTO obligations (
                    id, code, document_id, source_label, clause_ref, page, source_quote,
                    quote_verified, summary, actor, action, condition, frequency, deadline,
                    threshold, topic, criticality, applicability, applicability_reason, coverage,
                    review_status
                ) VALUES (
                    :id, :code, :document_id, :source_label, :clause_ref, NULL, :source_quote,
                    :quote_verified, :summary, :actor, :action, :condition, :frequency, :deadline,
                    :threshold, :topic, :criticality, :applicability, :applicability_reason,
                    :coverage, 'suggested'
                )
            """),
            {
                "id": obligation_id,
                "code": f"OB-{next_ob:02d}",
                "document_id": document.id,
                "source_label": source_label,
                "clause_ref": draft.clause_ref[:64],
                "source_quote": draft.source_quote,
                "quote_verified": settled.verdict == Verdict.ACCEPTED,
                "summary": draft.action,
                "actor": (_specified(draft.actor) or NOT_SPECIFIED)[:128],
                "action": draft.action,
                "condition": _specified(draft.condition),
                "frequency": (_specified(draft.frequency) or "")[:64] or None,
                "deadline": (_specified(draft.deadline) or "")[:64] or None,
                "threshold": (_specified(draft.threshold) or "")[:128] or None,
                "topic": draft.topic[:128],
                "criticality": factors.criticality,
                "applicability": draft.applicability,
                "applicability_reason": _specified(draft.applicability_reason),
                "coverage": coverage,
            },
        )
        renames[pipeline_code] = f"OB-{next_ob:02d}"
        next_ob += 1
        obligation_ids[pipeline_code] = obligation_id
        obligation_topics[pipeline_code] = draft.topic

    mappings = 0
    for mapping in result.mappings:
        control = controls.get(mapping.control_code)
        obligation_id = obligation_ids.get(mapping.obligation_code)
        if mapping.judgement is None or control is None or obligation_id is None:
            continue
        passed = mapping.verdict == Verdict.ACCEPTED
        session.execute(
            text("""
                INSERT INTO mappings (
                    id, obligation_id, control_id, coverage, rationale, graph_path, critic, status
                ) VALUES (
                    :id, :obligation_id, :control_id, :coverage, :rationale,
                    CAST(:graph_path AS jsonb), :critic, :status
                )
            """),
            {
                "id": f"map-{uuid.uuid4().hex[:10]}",
                "obligation_id": obligation_id,
                "control_id": control.id,
                "coverage": mapping.judgement.coverage,
                "rationale": mapping.judgement.rationale,
                "graph_path": json.dumps(
                    [f"Clause {mapping.obligation_code}", "Obligation", f"Control {control.code}"]
                ),
                "critic": "passed" if passed else "failed",
                "status": "suggested" if passed else "needs_review",
            },
        )
        mappings += 1

    gap_ids: dict[str, str] = {}
    next_gap = _next_number(session, "gaps", "G")
    for pipeline_code, gap in gap_by_obligation.items():
        obligation_id = obligation_ids.get(pipeline_code)
        if obligation_id is None:
            continue
        topic = obligation_topics[pipeline_code]
        score, priority, factors = calculate_risk(
            topic=f"{topic} {document.title}", gap_type=gap.gap_type
        )  # type: ignore[arg-type]
        control_ids = [
            controls[m.control_code].id
            for m in _relevant(judged.get(pipeline_code, []))
            if m.control_code in controls
        ]
        gap_id = f"g-{uuid.uuid4().hex[:10]}"
        session.execute(
            text("""
                INSERT INTO gaps (
                    id, code, obligation_id, gap_type, title, description, control_ids,
                    evidence_ids, origin, risk_factors, risk_score, priority, status
                ) VALUES (
                    :id, :code, :obligation_id, :gap_type, :title, :description,
                    CAST(:control_ids AS jsonb), '[]'::jsonb, 'initial',
                    CAST(:risk_factors AS jsonb), :risk_score, :priority, 'potential'
                )
            """),
            {
                "id": gap_id,
                "code": f"G-{next_gap:02d}",
                "obligation_id": obligation_id,
                "gap_type": gap.gap_type,
                "title": f"{topic[:1].upper()}{topic[1:]}: {_GAP_LABEL[gap.gap_type]}"[:255],
                "description": gap.description,
                "control_ids": json.dumps(control_ids),
                "risk_factors": factors.model_dump_json(),
                "risk_score": score,
                "priority": priority,
            },
        )
        renames[gap.code] = f"G-{next_gap:02d}"
        next_gap += 1
        gap_ids[gap.code] = gap_id

    remediations = 0
    for settled in result.remediations:
        gap_id = gap_ids.get(settled.key)
        if settled.draft is None or gap_id is None:
            continue
        _insert_remediation(session, gap_id, settled.draft, renames)
        remediations += 1

    session.execute(
        text("UPDATE documents SET status = 'ready', error = NULL WHERE id = :id"),
        {"id": document.id},
    )
    return {
        "obligations": len(obligation_ids),
        "mappings": mappings,
        "gaps": len(gap_ids),
        "remediations": remediations,
    }


def _rename(text_value: str, renames: dict[str, str]) -> str:
    if not renames:
        return text_value
    codes = "|".join(map(re.escape, sorted(renames, key=len, reverse=True)))
    pattern = re.compile(rf"\b({codes})\b")
    return pattern.sub(lambda m: renames[m.group(1)], text_value)


def _insert_remediation(
    session: Session,
    gap_id: str,
    draft: RemediationDraft,
    renames: dict[str, str] | None = None,
) -> None:
    names = renames or {}
    session.execute(
        text("""
            INSERT INTO remediations (
                id, gap_id, action, owner_team, target_days, closure_evidence, status
            ) VALUES (
                :id, :gap_id, :action, :owner_team, :target_days, :closure_evidence, 'draft'
            )
        """),
        {
            "id": f"rem-{uuid.uuid4().hex[:10]}",
            "gap_id": gap_id,
            "action": _rename(draft.action, names),
            "owner_team": draft.owner_team[:128],
            "target_days": min(max(draft.target_days, 1), 365),
            "closure_evidence": _rename(draft.closure_evidence, names),
        },
    )


def _draft_missing_remediations(
    session: Session, provider: StructuredLLMProvider, limit: int, totals: _Totals
) -> int:
    """Drafts fixes for open gaps that have none yet, e.g. when an earlier draft call failed."""
    names = {
        r["id"]: r["name"]
        for r in session.execute(text("SELECT id, name FROM controls")).mappings()
    }
    rows = session.execute(
        text("""
            SELECT g.id, g.code, g.gap_type, g.description, g.control_ids,
                   o.code AS obligation_code
            FROM gaps g JOIN obligations o ON o.id = g.obligation_id
            WHERE g.status <> 'dismissed'
              AND NOT EXISTS (SELECT 1 FROM remediations r WHERE r.gap_id = g.id)
            ORDER BY g.risk_score DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).mappings()
    gap_ids: dict[str, str] = {}
    gaps: list[GapInput] = []
    for row in rows:
        control_ids = row["control_ids"]
        if isinstance(control_ids, str):
            control_ids = json.loads(control_ids)
        gap_ids[row["code"]] = row["id"]
        gaps.append(
            GapInput(
                code=row["code"],
                obligation_code=row["obligation_code"],
                gap_type=row["gap_type"],
                description=row["description"],
                control_names=tuple(names[c] for c in control_ids if c in names),
            )
        )
    if not gaps:
        return 0

    started = datetime.now(UTC)
    metered = usage_of(provider)
    try:
        outcome = draft_remediation(provider, gaps)
    except LLMProviderError as exc:
        totals.record(
            NodeRecord(
                node="draft_remediation",
                status="failed",
                started_at=started,
                ended_at=datetime.now(UTC),
                llm_calls=1,
                error=str(exc),
                usage=usage_of(provider) - metered,
            ),
            f"Earlier gaps: drafting failed for {len(gaps)}",
        )
        return 0
    drafted = 0
    for settled in outcome.drafts:
        gap_id = gap_ids.get(settled.key)
        if settled.draft is not None and gap_id is not None:
            _insert_remediation(session, gap_id, settled.draft)
            drafted += 1
    totals.record(
        NodeRecord(
            node="draft_remediation",
            status="ok",
            started_at=started,
            ended_at=datetime.now(UTC),
            llm_calls=outcome.llm_calls,
            usage=usage_of(provider) - metered,
        ),
        f"Earlier gaps: {drafted} remediation drafts",
    )
    return drafted


# ---------------------------------------------------------------- execute


def _node_rows(
    totals: _Totals,
    run_started: datetime,
    failed: str | None,
    idle_note: str = "Skipped: nothing to do at this step.",
    *,
    with_change: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in _run_nodes(with_change or CHANGE_NODE in totals.records):
        conditional = node in CONDITIONAL_NODES
        records = totals.records.get(node, [])
        notes = totals.notes.get(node, [])
        if records:
            first = min(r.started_at for r in records)
            errors = [r.error for r in records if r.error]
            rows.append(
                {
                    "node": node,
                    "status": "failed" if errors else "done",
                    "offset_ms": int((first - run_started).total_seconds() * 1000),
                    "duration_ms": int(
                        sum((r.ended_at - r.started_at).total_seconds() for r in records) * 1000
                    ),
                    "llm_calls": sum(r.llm_calls for r in records),
                    "input_tokens": sum(r.usage.input_tokens for r in records),
                    "output_tokens": sum(r.usage.output_tokens for r in records),
                    "note": "; ".join(errors or notes) or None,
                    "conditional": conditional,
                }
            )
        else:
            rows.append(
                {
                    "node": node,
                    "status": "failed" if failed else "done",
                    "offset_ms": 0,
                    "duration_ms": 0,
                    "llm_calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "note": failed or idle_note,
                    "conditional": conditional,
                }
            )
    return rows


def _finish(
    session_factory: sessionmaker[Session],
    run_id: str,
    status: str,
    nodes: list[dict[str, Any]],
    cache_hits: int,
) -> None:
    with session_factory() as session, session.begin():
        session.execute(
            text("""
                UPDATE agent_runs
                SET status = :status, nodes = CAST(:nodes AS jsonb), cache_hits = :cache_hits
                WHERE id = :id
            """),
            {"id": run_id, "status": status, "nodes": json.dumps(nodes), "cache_hits": cache_hits},
        )


def _run_change(
    session_factory: sessionmaker[Session],
    settings: Settings,
    provider: StructuredLLMProvider,
    document: _Document,
    actor: ActorInfo,
    totals: _Totals,
) -> int:
    """Runs the change branch for one superseding document in its own transaction. A failure
    is recorded on the node and rolled back; it never stops the rest of the run."""
    started = datetime.now(UTC)
    try:
        with session_factory() as session, session.begin():
            outcome = run_change_branch(session, settings, provider, document.id, actor)
    except Exception as exc:
        logger.exception("change detection failed", extra={"document_id": document.id})
        totals.record(
            NodeRecord(
                node=CHANGE_NODE,
                status="failed",
                started_at=started,
                ended_at=datetime.now(UTC),
                llm_calls=0,
                error=f"Change detection stopped: {type(exc).__name__}. See the server log.",
            ),
            f"{document.title[:40]}: failed",
        )
        return 0
    totals.record(outcome.record, outcome.note)
    return outcome.counts.get("changes", 0)


def execute_run(
    session_factory: sessionmaker[Session],
    settings: Settings,
    run_id: str,
    actor: ActorInfo,
    request: RunRequest,
    provider_factory: Callable[[Settings], StructuredLLMProvider] = build_provider,
) -> None:
    """Background task: runs the pipeline per document and stores the results. Never raises."""
    run_started = datetime.now(UTC)
    totals = _Totals()
    provider: StructuredLLMProvider | None = None
    superseding: list[_Document] = []
    try:
        provider = provider_factory(settings)
        with session_factory() as session:
            documents = _documents(session, request)
            controls, controls_by_code = _controls(session)
        superseding = [d for d in documents if d.supersedes_id]
        stored: dict[str, int] = {"obligations": 0, "mappings": 0, "gaps": 0, "remediations": 0}
        for document in documents:
            with session_factory() as session, session.begin():
                paragraphs = _paragraphs(session, document)
                done = _already_read(session, document.id)
                fresh = [p for p in paragraphs if p.ref not in done]
                chosen = select_paragraphs(
                    fresh,
                    only=set(request.paragraphs) or None,
                    limit=settings.pipeline_max_paragraphs,
                )
                if not chosen:
                    continue
                for batch in batch_by_size(chosen, settings.pipeline_batch_chars):
                    result = run_pipeline(
                        provider,
                        clauses=[ClauseInput(clause_ref=p.ref, text=p.text) for p in batch],
                        controls=controls,
                        candidate_finder=keyword_candidates,
                        gap_builder=make_gap_builder(controls_by_code),
                        institution=settings.institution_profile,
                    )
                    totals.add(result, document.title[:40])
                    counts = _persist(session, document, result, controls_by_code)
                    for key, value in counts.items():
                        stored[key] += value

        # Change branch: after the document's own pipeline, so its obligations exist for the
        # impact analysis, and before remediation drafting, so change-driven gaps get drafts.
        for document in superseding:
            stored["changes"] = stored.get("changes", 0) + _run_change(
                session_factory, settings, provider, document, actor, totals
            )

        with session_factory() as session, session.begin():
            stored["remediations"] += _draft_missing_remediations(
                session, provider, settings.pipeline_max_paragraphs, totals
            )

        with session_factory() as session, session.begin():
            record_audit(
                session,
                actor=actor,
                action="Completed pipeline run",
                entity_type="pipeline",
                entity_code=run_id,
                after=stored,
            )
            rebuild_kg(session)
        try:
            run_evaluation(settings)
        except Exception:
            # Scoring is a report on the run, never a reason to fail it.
            logger.exception("accuracy evaluation failed", extra={"run_id": run_id})
        failed = any(r.error for records in totals.records.values() for r in records)
        usage = getattr(provider, "usage", None)
        hits = usage().cache_hits if callable(usage) else 0
        _finish(
            session_factory,
            run_id,
            "failed" if failed else "done",
            _node_rows(
                totals,
                run_started,
                None,
                idle_note=(
                    "Skipped: nothing to do at this step."
                    if documents
                    else "Skipped: no new regulation documents to analyse."
                ),
                with_change=bool(superseding),
            ),
            hits,
        )
    except Exception as exc:
        logger.exception("pipeline run failed", extra={"run_id": run_id})
        message = (
            str(exc)
            if isinstance(exc, PipelineNotConfiguredError)
            else f"Run stopped: {type(exc).__name__}. See the server log."
        )
        _finish(
            session_factory,
            run_id,
            "failed",
            _node_rows(totals, run_started, message, with_change=bool(superseding)),
            0,
        )
