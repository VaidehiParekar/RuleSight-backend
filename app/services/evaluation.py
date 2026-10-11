"""Scores the pipeline's stored results against the labelled answer key.

Only documents that were uploaded and processed by the pipeline are scored (they have a stored
file). Hand-seeded demo rows have no file and are ignored, so the numbers measure the agents, not
the seed data. Every metric is a ratio in [0, 1]; a metric with nothing to measure is left out
rather than reported as 0 or 1.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.schemas.domain import EvalMetric, EvalReport
from app.workflows.critic import quote_in

# Answer-key "source" -> words that must all appear in an uploaded document's title, reference,
# version label or file name for it to be that source. Each inner tuple is "any of".
SOURCE_MATCHERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "RBI KYC MD 2016": (("kyc",),),
    "RBI NSM v2 (2026)": (("note sorting", "nsm"), ("2026",)),
}

GAP_TYPES = {
    "design": "design",
    "missing": "missing",
    "operating": "operating",
    "design + operating": "design_operating",
    "insufficient info": "insufficient_info",
}

_STOP = {
    "must",
    "shall",
    "with",
    "that",
    "this",
    "from",
    "have",
    "been",
    "into",
    "under",
    "every",
    "least",
    "their",
    "they",
    "where",
    "which",
    "whose",
    "than",
    "more",
    "only",
    "also",
    "such",
}


@dataclass(frozen=True)
class Expected:
    key: str
    source: str
    paragraphs: frozenset[int]
    summary: str
    applicable: bool
    control: str | None
    gap_type: str | None


@dataclass(frozen=True)
class Found:
    id: str
    document_text: str
    paragraph: int | None
    words: frozenset[str]
    source_quote: str
    applicable: bool
    controls: frozenset[str]
    gap_type: str | None
    sources: frozenset[str]


@dataclass
class Score:
    matched: dict[str, str] = field(default_factory=dict)  # expected key -> found id
    metrics: list[EvalMetric] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def words(text: str) -> frozenset[str]:
    return frozenset(
        w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 4 and w not in _STOP
    )


def paragraph_numbers(label: str) -> frozenset[int]:
    """Top-level paragraph numbers in an answer-key label: "18(a)(iv)" -> {18},
    "2.2 / 4" -> {2, 4}, "5 (Tables 1-3)" -> {5}, "Testing Procedure" -> {}."""
    without_notes = re.sub(r"\([^)]*\)", " ", label)
    return frozenset(int(m) for m in re.findall(r"(?<![\d.])(\d+)(?:\.\d+)?", without_notes))


def leading_number(clause_ref: str) -> int | None:
    match = re.match(r"\s*(\d+)", clause_ref)
    return int(match.group(1)) if match else None


def load_expected(path: Path) -> list[Expected]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected: list[Expected] = []
    for row in rows:
        control = row["control_id"].strip()
        gap = row["gap_type"].strip().lower()
        expected.append(
            Expected(
                key=row["obligation_id"].strip(),
                source=row["source"].strip(),
                paragraphs=paragraph_numbers(row["paragraph"]),
                summary=row["obligation_summary"],
                applicable=row["applicability"].strip().lower().startswith("applicable"),
                control=None if control.upper() in {"", "NONE"} else control.upper(),
                gap_type=GAP_TYPES.get(gap) if gap else None,
            )
        )
    return expected


def document_sources(descriptor: str) -> frozenset[str]:
    """Answer-key sources a document matches, from its title, reference, version and file."""
    text = descriptor.lower()
    return frozenset(
        source
        for source, groups in SOURCE_MATCHERS.items()
        if all(any(term in text for term in group) for group in groups)
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def score(expected: Sequence[Expected], found: Sequence[Found]) -> Score:
    result = Score()
    in_scope_sources = {s for f in found for s in f.sources}
    targets = [e for e in expected if e.source in in_scope_sources]
    if not targets:
        result.notes.append("No uploaded document matches a source in the answer key yet.")
        return result

    taken: set[str] = set()
    pairs: list[tuple[Expected, Found]] = []
    for item in targets:
        candidates = [
            f
            for f in found
            if item.source in f.sources
            and f.id not in taken
            and (not item.paragraphs or f.paragraph in item.paragraphs)
        ]
        target_words = words(item.summary)
        best = max(candidates, key=lambda f: len(target_words & f.words), default=None)
        if best is None or not (target_words & best.words):
            continue
        taken.add(best.id)
        pairs.append((item, best))
        result.matched[item.key] = best.id

    # Precision counts only obligations from paragraphs the answer key covers; anything the agent
    # found elsewhere in the document is outside the labelled scope, not a false positive.
    key_paragraph_found = [
        f
        for f in found
        if any(
            e.source in f.sources and (not e.paragraphs or f.paragraph in e.paragraphs)
            for e in targets
        )
    ]
    expected_gaps = [e for e in targets if e.gap_type]
    found_gaps = [(e, f) for e, f in pairs if e.gap_type and f.gap_type]
    extra_gaps = [(e, f) for e, f in pairs if not e.gap_type and f.gap_type]
    gap_predictions = len(found_gaps) + len(extra_gaps)

    def control_ok(e: Expected, f: Found) -> bool:
        return (not f.controls) if e.control is None else e.control in f.controls

    quotes = [f for f in found if f.source_quote]
    candidates = {
        "obligation_recall": ("Obligation recall", _ratio(len(pairs), len(targets))),
        "obligation_precision": (
            "Obligation precision",
            _ratio(len(pairs), len(key_paragraph_found)),
        ),
        "applicability_accuracy": (
            "Applicability accuracy",
            _ratio(sum(e.applicable == f.applicable for e, f in pairs), len(pairs)),
        ),
        "mapping_accuracy": (
            "Mapping accuracy",
            _ratio(sum(control_ok(e, f) for e, f in pairs), len(pairs)),
        ),
        "gap_recall": ("Gap recall", _ratio(len(found_gaps), len(expected_gaps))),
        "gap_precision": ("Gap precision", _ratio(len(found_gaps), gap_predictions)),
        "gap_type_accuracy": (
            "Gap type accuracy",
            _ratio(sum(e.gap_type == f.gap_type for e, f in found_gaps), len(found_gaps)),
        ),
        "citation_validity": (
            "Citation validity",
            _ratio(sum(quote_in(f.source_quote, f.document_text) for f in quotes), len(quotes)),
        ),
    }
    for key, (label, value) in candidates.items():
        if value is not None:
            result.metrics.append(EvalMetric(key=key, label=label, value=value))
    result.notes.append(
        f"{len(pairs)} of {len(targets)} answer-key obligations matched "
        f"in {', '.join(sorted(in_scope_sources))}."
    )
    return result


def report(result: Score, answer_key: Path, scored: Iterable[str]) -> EvalReport:
    documents = ", ".join(scored) or "none"
    method = (
        f"Measured against {answer_key.as_posix()} on documents processed by the pipeline "
        f"({documents}). Seeded demo rows are excluded. Obligations are matched one-to-one by "
        "source, paragraph number and shared key terms. Citation validity re-checks every stored "
        "quote against the document text in code. " + " ".join(result.notes)
    )
    return EvalReport(
        is_mock=False,
        scored_at=datetime.now(UTC).isoformat(),
        method=method,
        metrics=result.metrics,
    )


def load_found(database_url: str) -> tuple[list[Found], list[str]]:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        documents = (
            conn.execute(
                text("""
                SELECT id, title, COALESCE(reference, '') AS reference, version_label,
                       COALESCE(file_path, '') AS file_path
                FROM documents
                WHERE doc_type = 'regulation' AND file_path IS NOT NULL
            """)
            )
            .mappings()
            .all()
        )
        found: list[Found] = []
        scored: list[str] = []
        for doc in documents:
            descriptor = " ".join(
                [doc["title"], doc["reference"], doc["version_label"], Path(doc["file_path"]).name]
            )
            sources = document_sources(descriptor)
            if not sources:
                continue
            body = "\n".join(
                r[0]
                for r in conn.execute(
                    text("SELECT text FROM chunks WHERE document_id = :id"), {"id": doc["id"]}
                )
            )
            rows = conn.execute(
                text("""
                    SELECT o.id, o.clause_ref, o.summary, o.topic, o.source_quote, o.applicability,
                           COALESCE(
                               (SELECT json_agg(c.code) FROM mappings m
                                JOIN controls c ON c.id = m.control_id
                                WHERE m.obligation_id = o.id
                                  AND m.coverage IN ('covered', 'partial')), '[]'
                           ) AS controls,
                           (SELECT g.gap_type FROM gaps g WHERE g.obligation_id = o.id
                            ORDER BY g.risk_score DESC LIMIT 1) AS gap_type
                    FROM obligations o WHERE o.document_id = :id
                """),
                {"id": doc["id"]},
            ).mappings()
            for r in rows:
                controls = (
                    r["controls"] if isinstance(r["controls"], list) else json.loads(r["controls"])
                )
                number = r["clause_ref"].strip().split("(")[0].split(".")[0]
                found.append(
                    Found(
                        id=r["id"],
                        document_text=body,
                        paragraph=int(number) if number.isdigit() else None,
                        words=words(f"{r['summary']} {r['topic']} {r['source_quote']}"),
                        source_quote=r["source_quote"],
                        applicable=r["applicability"] != "not_applicable",
                        controls=frozenset(c.upper() for c in controls),
                        gap_type=r["gap_type"],
                        sources=sources,
                    )
                )
            scored.append(doc["title"])
    engine.dispose()
    return found, scored


def run_evaluation(settings: Settings) -> EvalReport | None:
    """Scores the database and saves the report. None when no answer key or report path is set."""
    if settings.answer_key_path is None or settings.eval_report_path is None:
        return None
    found, scored = load_found(settings.database_url.get_secret_value())
    result = report(
        score(load_expected(settings.answer_key_path), found), settings.answer_key_path, scored
    )
    settings.eval_report_path.parent.mkdir(parents=True, exist_ok=True)
    settings.eval_report_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result
