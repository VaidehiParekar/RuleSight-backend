"""The change branch of a pipeline run: runs when the analysed document supersedes another.

It compares the two versions (app.workflows.change), stores the changes, marks withdrawn
documents as superseded, records withdrawn circulars that are not in the corpus, and works out
the impact: changed clause -> obligations -> mappings -> controls. A new or stricter obligation
that no control covers becomes a gap with origin 'change' (urgency 1.5 in the risk formula).

Nothing is final: changes the critic could not verify are stored flagged "Needs review" and never
produce gaps. Already-detected pairs are skipped, so a rerun never duplicates rows.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.config import Settings
from app.core.rules import calculate_risk, evaluate_gap_type
from app.integrations.llm.base import StructuredLLMProvider, usage_of
from app.schemas.domain import Applicability, Coverage, GapType
from app.services.regulation_text import extract_text
from app.workflows.change import (
    AnnexMatch,
    ChangeOptions,
    ChangeReport,
    CorpusDocument,
    DetectedChange,
    DocumentVersion,
    annex_row_for,
    detect_changes,
    parse_date,
    withdrawal_watermark,
)
from app.workflows.critic import Verdict, normalise, quote_in
from app.workflows.pipeline import AgentRun as NodeRecord

logger = logging.getLogger(__name__)

CHANGE_NODE = "detect_changes"

_GAP_LABEL = {
    "missing": "no control in place",
    "design": "control design falls short",
    "operating": "control not operating as designed",
    "design_operating": "control design and operation fall short",
    "insufficient_info": "not enough information to confirm",
}
_REVIEW_PREFIX = "Needs review: "
# Coverage values that tie a control to an obligation for impact purposes.
_LINKED = ("covered", "partial", "insufficient_info")


@dataclass
class ChangeOutcome:
    record: NodeRecord
    note: str
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class _Doc:
    id: str
    title: str
    reference: str | None
    version_label: str
    supersedes_id: str | None
    file_path: str | None
    status: str


@dataclass(frozen=True)
class _Obligation:
    id: str
    code: str
    clause_ref: str
    source_quote: str
    topic: str
    applicability: str


# ---------------------------------------------------------------- loading


def _doc(session: Session, document_id: str) -> _Doc | None:
    row = (
        session.execute(
            text("""
                SELECT id, title, reference, version_label, supersedes_id, file_path, status
                FROM documents WHERE id = :id
            """),
            {"id": document_id},
        )
        .mappings()
        .first()
    )
    return _Doc(**dict(row)) if row else None


def _text(session: Session, doc: _Doc, *, chunk_limit: int | None = None) -> str:
    """Full text from the stored file, or the saved chunks when there is no file."""
    if doc.file_path and Path(doc.file_path).is_file():
        return extract_text(Path(doc.file_path).read_bytes(), doc.file_path)
    rows = session.execute(
        text("""
            SELECT text FROM chunks WHERE document_id = :id
            ORDER BY created_at, id LIMIT :limit
        """),
        {"id": doc.id, "limit": chunk_limit},
    )
    return "\n\n".join(r[0] for r in rows)


def _corpus(session: Session, new_id: str) -> list[CorpusDocument]:
    rows = session.execute(
        text("""
            SELECT id, title, reference, version_label, supersedes_id, file_path, status
            FROM documents WHERE doc_type = 'regulation' AND id <> :id ORDER BY created_at
        """),
        {"id": new_id},
    ).mappings()
    docs = [_Doc(**dict(r)) for r in rows]
    # Only the letterhead is used for matching, so a few chunks are enough.
    return [
        CorpusDocument(
            id=d.id,
            title=d.title,
            reference=d.reference or "",
            version_label=d.version_label,
            text=_text(session, d, chunk_limit=3),
        )
        for d in docs
    ]


def _obligations(session: Session, document_id: str) -> list[_Obligation]:
    rows = session.execute(
        text("""
            SELECT id, code, clause_ref, source_quote, topic, applicability
            FROM obligations WHERE document_id = :id ORDER BY code
        """),
        {"id": document_id},
    ).mappings()
    return [_Obligation(**dict(r)) for r in rows]


def _bare(ref: str) -> str:
    return ref.strip().removeprefix("para").strip()


def obligations_at(
    obligations: Iterable[_Obligation], ref: str | None, unit_text: str | None
) -> list[_Obligation]:
    """Obligations extracted from a changed unit: same clause number (or a sub-clause of it), or
    whose verified quote lies inside the unit's text (the pipeline may store '8' for '8.2')."""
    if not ref:
        return []
    target = _bare(ref)
    found: list[_Obligation] = []
    for ob in obligations:
        own = _bare(ob.clause_ref)
        if (
            own == target
            or own.startswith(f"{target}.")
            or (unit_text and quote_in(ob.source_quote, unit_text))
        ):
            found.append(ob)
    return found


def _linked_controls(session: Session, obligation_ids: Sequence[str]) -> dict[str, list[Any]]:
    """Per obligation: (control code, coverage) of its mappings that were not rejected."""
    if not obligation_ids:
        return {}
    rows = session.execute(
        text("""
            SELECT m.obligation_id, m.coverage, c.code
            FROM mappings m JOIN controls c ON c.id = m.control_id
            WHERE m.obligation_id = ANY(:ids) AND m.status <> 'rejected'
            ORDER BY c.code
        """),
        {"ids": list(obligation_ids)},
    ).mappings()
    grouped: dict[str, list[Any]] = {}
    for r in rows:
        grouped.setdefault(r["obligation_id"], []).append((r["code"], r["coverage"]))
    return grouped


# ---------------------------------------------------------------- persistence helpers


def _next_number(session: Session, table: str, column: str, prefix: str) -> int:
    row = session.execute(
        text(
            f"SELECT COALESCE(MAX(CAST(SUBSTRING({column} FROM :pattern) AS INTEGER)), 0) "  # noqa: S608 - table and column are module constants
            f"FROM {table}"
        ),
        {"pattern": f"^{prefix}-([0-9]+)$"},
    ).scalar_one()
    return int(row) + 1


def _clip(value: str | None, size: int) -> str | None:
    return None if value is None else value[:size]


@dataclass
class _Writer:
    session: Session
    old: _Doc
    new: _Doc
    next_change: int
    ids: list[str] = field(default_factory=list)

    def insert(
        self,
        *,
        clause_ref: str,
        change_type: str,
        title: str,
        summary: str,
        significance: str,
        old_text: str | None = None,
        new_text: str | None = None,
        carried_over: Sequence[str] = (),
        impact: dict[str, Any] | None = None,
    ) -> str:
        change_id = f"chn-{self.next_change:02d}"
        self.next_change += 1
        self.session.execute(
            text("""
                INSERT INTO changes (
                    id, old_document_id, new_document_id, clause_ref, change_type, title,
                    old_text, new_text, summary, significance, carried_over, impact
                ) VALUES (
                    :id, :old_id, :new_id, :clause_ref, :change_type, :title, :old_text,
                    :new_text, :summary, :significance, CAST(:carried_over AS jsonb),
                    CAST(:impact AS jsonb)
                )
            """),
            {
                "id": change_id,
                "old_id": self.old.id,
                "new_id": self.new.id,
                "clause_ref": clause_ref[:64] or "-",
                "change_type": change_type,
                "title": title[:255],
                "old_text": normalise(old_text) if old_text else None,
                "new_text": normalise(new_text) if new_text else None,
                "summary": summary,
                "significance": significance,
                "carried_over": json.dumps(list(carried_over)),
                "impact": json.dumps(impact or {"obligations": [], "controls": [], "gaps": []}),
            },
        )
        self.ids.append(change_id)
        return change_id

    def set_impact(self, change_id: str, impact: dict[str, Any]) -> None:
        self.session.execute(
            text("UPDATE changes SET impact = CAST(:impact AS jsonb) WHERE id = :id"),
            {"id": change_id, "impact": json.dumps(impact)},
        )


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


# ---------------------------------------------------------------- impact and gaps


def _change_gaps(
    session: Session,
    *,
    change_id: str,
    change: DetectedChange,
    obligations: Sequence[_Obligation],
    links: dict[str, list[Any]],
    new: _Doc,
) -> list[str]:
    """Gaps for new or stricter obligations not covered. An open gap this run already found for
    the obligation is re-tagged as change-driven (urgency 1.5) rather than duplicated."""
    codes: list[str] = []
    next_gap = _next_number(session, "gaps", "code", "G")
    for ob in obligations:
        topic = f"{ob.topic} {new.title}"
        open_gaps = (
            session.execute(
                text("""
                    SELECT id, code, gap_type, origin FROM gaps
                    WHERE obligation_id = :id AND status <> 'dismissed' ORDER BY code
                """),
                {"id": ob.id},
            )
            .mappings()
            .all()
        )
        if open_gaps:
            for gap in open_gaps:
                if gap["origin"] == "initial":
                    score, priority, factors = calculate_risk(
                        topic=topic, gap_type=cast("GapType", gap["gap_type"]), origin="change"
                    )
                    session.execute(
                        text("""
                            UPDATE gaps SET origin = 'change', change_id = :change_id,
                                risk_score = :score, priority = :priority,
                                risk_factors = CAST(:factors AS jsonb)
                            WHERE id = :id
                        """),
                        {
                            "id": gap["id"],
                            "change_id": change_id,
                            "score": score,
                            "priority": priority,
                            "factors": factors.model_dump_json(),
                        },
                    )
                codes.append(gap["code"])
            continue
        coverages = [cast("Coverage", cov) for _, cov in links.get(ob.id, [])]
        gap_type = evaluate_gap_type(cast("Applicability", ob.applicability), coverages)
        if gap_type is None:
            continue
        score, priority, factors = calculate_risk(topic=topic, gap_type=gap_type, origin="change")
        control_ids = [
            r[0]
            for r in session.execute(
                text("""
                    SELECT DISTINCT m.control_id FROM mappings m
                    WHERE m.obligation_id = :id AND m.status <> 'rejected'
                      AND m.coverage IN ('covered', 'partial')
                """),
                {"id": ob.id},
            )
        ]
        code = f"G-{next_gap:02d}"
        next_gap += 1
        session.execute(
            text("""
                INSERT INTO gaps (
                    id, code, obligation_id, gap_type, title, description, control_ids,
                    evidence_ids, origin, change_id, risk_factors, risk_score, priority, status
                ) VALUES (
                    :id, :code, :obligation_id, :gap_type, :title, :description,
                    CAST(:control_ids AS jsonb), '[]'::jsonb, 'change', :change_id,
                    CAST(:risk_factors AS jsonb), :risk_score, :priority, 'potential'
                )
            """),
            {
                "id": f"g-{uuid.uuid4().hex[:10]}",
                "code": code,
                "obligation_id": ob.id,
                "change_id": change_id,
                "gap_type": gap_type,
                "title": f"{ob.topic[:1].upper()}{ob.topic[1:]}: {_GAP_LABEL[gap_type]}"[:255],
                "description": f"Introduced or tightened by {change_id.upper()}: {change.summary}",
                "control_ids": json.dumps(control_ids),
                "risk_factors": factors.model_dump_json(),
                "risk_score": score,
                "priority": priority,
            },
        )
        codes.append(code)
    return codes


def _impact(
    session: Session,
    *,
    change_id: str,
    change: DetectedChange,
    old_obligations: Sequence[_Obligation],
    new_obligations: Sequence[_Obligation],
    new: _Doc,
) -> dict[str, Any]:
    """Changed clause -> obligations (old and new version) -> mappings -> controls -> gaps."""
    old_hit = obligations_at(old_obligations, change.old_ref, change.old_text)
    new_hit = obligations_at(new_obligations, change.new_ref, change.new_text)
    links = _linked_controls(session, [o.id for o in [*old_hit, *new_hit]])
    controls = _unique(
        code for ob in [*old_hit, *new_hit] for code, cov in links.get(ob.id, []) if cov in _LINKED
    )
    gaps: list[str] = []
    notes: list[str] = []
    stricter = change.kind in ("modified", "added") and change.significance != "administrative"
    if change.verdict != Verdict.ACCEPTED:
        notes.append("Not verified by the critic, so no gaps were raised.")
    elif stricter:
        gaps = _change_gaps(
            session,
            change_id=change_id,
            change=change,
            obligations=[o for o in new_hit if o.applicability == "applicable"],
            links=links,
            new=new,
        )
        if not new_hit:
            notes.append(
                f"No obligations have been extracted from clause {change.new_ref} yet; "
                "run the pipeline on it to assess coverage."
            )
    if old_hit and change.kind in ("modified", "removed"):
        notes.append(
            "Controls mapped to the old obligation(s) "
            f"{', '.join(o.code for o in old_hit)} should be reviewed against the new text."
        )
    return {
        "obligations": _unique(o.code for o in [*old_hit, *new_hit]),
        "controls": controls,
        "gaps": _unique(gaps),
        "note": " ".join(notes) or None,
    }


# ---------------------------------------------------------------- annex


def _withdrawn_note(report: ChangeReport, new: _Doc, row: int | None) -> str:
    when = report.issue_date or "the date of issue"
    source = report.circular_number or new.reference or new.title
    where = f", Annex row {row}" if row is not None else ""
    return f"Withdrawn from {when} by {new.title} ({source}){where}."


def _supersede(session: Session, document_ids: Sequence[str], note: str) -> list[str]:
    """Marks documents superseded. Documents already superseded keep their status and note."""
    if not document_ids:
        return []
    rows = session.execute(
        text("""
            UPDATE documents SET status = 'superseded', withdrawn_note = COALESCE(withdrawn_note, :note)
            WHERE id = ANY(:ids) AND status <> 'superseded'
            RETURNING id
        """),
        {"ids": list(document_ids), "note": note},
    )
    return [r[0] for r in rows]


def _persist_annex(
    session: Session,
    writer: _Writer,
    report: ChangeReport,
    corpus: Sequence[CorpusDocument],
) -> tuple[int, int, list[str]]:
    titles = {d.id: d.title for d in corpus}
    texts = {d.id: d.text for d in corpus}
    superseded: list[str] = []
    withdrawn = 0
    for match in (m for m in report.annex if m.in_corpus):
        row = match.row
        stamps = _unique(
            stamp for doc_id in match.document_ids if (stamp := withdrawal_watermark(texts[doc_id]))
        )
        summary = (
            f"The new version's Annex (row {row.row}) withdraws {row.reference} dated "
            f'{row.display_date} ("{row.subject}"). It matches '
            f"{', '.join(_unique(titles[d] for d in match.document_ids))} in the corpus, which "
            "RuleSight marked as superseded."
        )
        if stamps:
            summary += f" The document itself is stamped 'Withdrawn from {stamps[0]}'."
        writer.insert(
            clause_ref=f"Annex row {row.row}",
            change_type="withdrawn",
            title=f"Circular of {row.display_date} is withdrawn: {row.subject}",
            summary=summary,
            significance="medium",
            old_text=f"{row.reference} · {row.display_date} · {row.subject}",
            new_text=report.withdrawal_sentence,
        )
        withdrawn += 1
        superseded += _supersede(
            session, match.document_ids, _withdrawn_note(report, writer.new, row.row)
        )

    missing = [m for m in report.annex if not m.in_corpus]
    for match in missing:
        row = match.row
        session.execute(
            text("""
                INSERT INTO missing_circulars (
                    id, document_id, row_num, reference, circular_date, subject
                ) VALUES (:id, :document_id, :row_num, :reference, :circular_date, :subject)
            """),
            {
                "id": f"mc-{uuid.uuid4().hex[:10]}",
                "document_id": writer.new.id,
                "row_num": row.row,
                "reference": row.reference[:255],
                "circular_date": row.display_date[:64],
                "subject": row.subject,
            },
        )
    if missing:
        latest = _latest(missing)
        listed = "; ".join(f"{m.row.reference} ({m.row.display_date})" for m in missing)
        summary = (
            f"The Annex withdraws {len(report.annex)} circulars; {len(missing)} are not in the "
            f"corpus: {listed}. RuleSight has not read them and does not infer what they say."
        )
        if latest is not None:
            summary += (
                f" The most recent missing circular, dated {latest.row.display_date} "
                f'("{latest.row.subject}"), is not ingested, so the history of these '
                "instructions may be incomplete."
            )
        writer.insert(
            clause_ref="Annex",
            change_type="corpus_gap",
            title=f"{len(missing)} withdrawn circulars are not in the corpus",
            summary=summary,
            significance="medium",
        )
    return withdrawn, len(missing), superseded


def _latest(matches: Sequence[AnnexMatch]) -> AnnexMatch | None:
    dated = [(parse_date(m.row.date), m) for m in matches]
    known = [(d, m) for d, m in dated if d is not None]
    return max(known, key=lambda item: item[0])[1] if known else None


# ---------------------------------------------------------------- entry point


def _review_text(change: DetectedChange) -> tuple[str, str]:
    if change.verdict == Verdict.ACCEPTED:
        return change.title, change.summary
    problems = "; ".join(change.problems)[:400]
    return (
        f"{_REVIEW_PREFIX}{change.title}",
        f"{change.summary} (Critic could not verify this finding: {problems})".strip(),
    )


def _consolidated(
    writer: _Writer,
    carried: Sequence[DetectedChange],
    new_obligations: Sequence[_Obligation],
    report: ChangeReport,
) -> None:
    verified = [c for c in carried if c.verdict == Verdict.ACCEPTED]
    flagged = [c for c in carried if c.verdict != Verdict.ACCEPTED]
    if not verified and not flagged:
        return
    codes = _unique(
        ob.code for c in verified for ob in obligations_at(new_obligations, c.new_ref, c.new_text)
    )
    listed = codes or [f"para {c.new_ref}" for c in verified]
    sources: list[str] = []
    for source in _unique(c.carried_from or "" for c in verified):
        if not source:
            continue
        row = annex_row_for(source, report.annex)
        sources.append(f"{source} (not in corpus)" if row and not row.in_corpus else source)
    refs = ", ".join(c.new_ref or "" for c in verified)
    summary = (
        f"Paragraphs {refs} restate requirements from {' and '.join(sources) or 'earlier instructions'}"
        ", as the new version itself states. They are consolidated, not new requirements."
        if verified
        else ""
    )
    if flagged:
        summary += (
            f" Paragraphs {', '.join(c.new_ref or '' for c in flagged)} were also labelled carried "
            "over, but the critic could not verify the quotes; they need review."
        )
    writer.insert(
        clause_ref=refs or ", ".join(c.new_ref or "" for c in flagged),
        change_type="consolidated",
        title=f"{len(verified)} requirements carried over, not new"
        if verified
        else f"{_REVIEW_PREFIX}requirements possibly carried over",
        summary=summary.strip(),
        significance="low",
        carried_over=listed if verified else [],
        impact={"obligations": codes, "controls": [], "gaps": []},
    )


def _already_detected(session: Session, old_id: str, new_id: str) -> bool:
    return (
        session.execute(
            text("""
                SELECT 1 FROM changes WHERE old_document_id = :old AND new_document_id = :new
                UNION ALL
                SELECT 1 FROM missing_circulars WHERE document_id = :new
                LIMIT 1
            """),
            {"old": old_id, "new": new_id},
        ).first()
        is not None
    )


def run_change_branch(
    session: Session,
    settings: Settings,
    provider: StructuredLLMProvider,
    document_id: str,
    actor: ActorInfo,
) -> ChangeOutcome:
    """Detects and stores the changes for one superseding document, inside the caller's
    transaction. Raises only for unexpected errors; model failures are reported in the record."""
    started = datetime.now(UTC)
    metered = usage_of(provider)

    def record(note: str, calls: int = 0, error: str | None = None) -> ChangeOutcome:
        return ChangeOutcome(
            record=NodeRecord(
                node=CHANGE_NODE,
                status="failed" if error else "ok",
                started_at=started,
                ended_at=datetime.now(UTC),
                llm_calls=calls,
                error=error,
                usage=usage_of(provider) - metered,
            ),
            note=note,
        )

    new = _doc(session, document_id)
    old = _doc(session, new.supersedes_id) if new and new.supersedes_id else None
    if new is None or old is None:
        return record("Skipped: the document does not supersede another.")
    label = new.title[:40]
    if _already_detected(session, old.id, new.id):
        return record(f"{label}: skipped, changes for this pair were already detected")

    old_text = _text(session, old)
    new_text = _text(session, new)
    corpus = _corpus(session, new.id)
    report = detect_changes(
        provider,
        old=DocumentVersion(old.id, old.title, old.reference or "", old.version_label, old_text),
        new=DocumentVersion(new.id, new.title, new.reference or "", new.version_label, new_text),
        corpus=corpus,
        options=ChangeOptions(
            min_ref_share=settings.change_same_structure_min_ref_share,
            min_heading_similarity=settings.change_same_structure_min_heading_similarity,
            max_units=settings.change_max_units,
        ),
    )

    writer = _Writer(session, old, new, _next_number(session, "changes", "id", "chn"))
    old_obligations = _obligations(session, old.id)
    new_obligations = _obligations(session, new.id)
    gap_codes: list[str] = []
    for change in report.changes:
        if change.kind == "carried_over":
            continue
        title, summary = _review_text(change)
        if change.kind == "added":
            title = (
                title
                if title.lower().startswith(("new", _REVIEW_PREFIX.lower()))
                else (f"New: {title}")
            )
        elif change.kind == "removed":
            title = f"Removed: {title}"
        # The UI's change types have no added/removed: both are modifications with one side empty.
        change_id = writer.insert(
            clause_ref=change.new_ref or change.old_ref or "-",
            change_type="modified",
            title=title,
            summary=summary,
            significance=change.significance,
            old_text=change.old_text,
            new_text=change.new_text,
        )
        impact = _impact(
            session,
            change_id=change_id,
            change=change,
            old_obligations=old_obligations,
            new_obligations=new_obligations,
            new=new,
        )
        writer.set_impact(change_id, impact)
        gap_codes += impact["gaps"]
    _consolidated(
        writer, [c for c in report.changes if c.kind == "carried_over"], new_obligations, report
    )
    withdrawn, missing, superseded = _persist_annex(session, writer, report, corpus)

    stamp = withdrawal_watermark(old_text)
    if old.status != "superseded" and old.id not in superseded:
        note = (
            _withdrawn_note(report, new, None)
            if stamp is None
            else f"Stamped 'Withdrawn from {stamp}'; superseded by {new.title}."
        )
        superseded += _supersede(session, [old.id], note)

    kinds = [c.kind for c in report.changes]
    review = sum(1 for c in report.changes if c.verdict != Verdict.ACCEPTED)
    counts = {
        "changes": len(writer.ids),
        "modified": kinds.count("modified"),
        "added": kinds.count("added"),
        "removed": kinds.count("removed"),
        "carried_over": kinds.count("carried_over"),
        "needs_review": review,
        "withdrawn_in_corpus": withdrawn,
        "missing_circulars": missing,
        "change_gaps": len(_unique(gap_codes)),
    }
    record_audit(
        session,
        actor=actor,
        action="Detected regulatory changes",
        entity_type="document",
        entity_code=new.title[:128],
        after={
            "compared_with": old.title,
            "mode": report.mode,
            "superseded": ", ".join(superseded) or "none",
            **{k: str(v) for k, v in counts.items()},
        },
    )
    note = (
        f"{label}: {report.mode} mode ({report.mode_reason}); {counts['modified']} modified, "
        f"{counts['added']} added, {counts['removed']} removed, {counts['carried_over']} carried "
        f"over, {review} need review; Annex: {withdrawn} withdrawn in corpus, {missing} not in "
        f"corpus; {counts['change_gaps']} change gaps"
    )
    if report.unresolved:
        note += f"; not classified: {', '.join(report.unresolved)}"
    # A failed model call still keeps the deterministic results (Annex, superseded versions).
    error = f"{report.error} Deterministic results kept: {note}" if report.error else None
    outcome = record(note, report.llm_calls, error)
    outcome.counts = counts
    return outcome
