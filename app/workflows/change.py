"""Change intelligence: what changed between two versions of an RBI instruction.

The workflow is pure. It receives document text and an injected model provider and returns plain
results; app.services.pipeline_runner stores them and works out the impact.

Two modes, chosen automatically by ``choose_mode``:

* ``clause`` (same structure, e.g. a revised Master Direction that keeps its numbering): units are
  aligned by paragraph number and ``difflib`` decides added / removed / modified. Whitespace-only
  differences are ignored. One batched model call then writes the title, summary and significance.
* ``obligation`` (different structure, e.g. a one-page circular replaced by a Master Direction):
  paragraph numbers mean nothing across the versions, so one batched model call labels every
  duty-stating unit modified / added / removed / carried-over against the other version, with
  keyword-overlap hints for likely counterparts.

Mode rule: the versions share a structure when at least ``min_ref_share`` of the paragraph numbers
(counted over the larger document) appear in both, and the shared paragraphs' headings (first
line) have a mean similarity of at least ``min_heading_similarity``. Otherwise the obligation mode
is used. The thresholds come from Settings.

Every model claim carries verbatim quotes that the critic checks in code (critic.check_change).
Failing items are sent back once; anything still failing is kept and flagged for review, never
silently accepted.

The new version's "circulars withdrawn / repealed" Annex is parsed without a model: each row is
matched against the corpus by its circular reference (or by date and subject). Matches are
withdrawn documents; rows with no match are reported as missing from the corpus.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Literal, cast

from app.integrations.llm.base import LLMProviderError, StructuredLLMProvider
from app.services.regulation_text import Paragraph, split_paragraphs
from app.workflows import prompts
from app.workflows.critic import Verdict, check_change, normalise, verdict_for
from app.workflows.schemas import ChangeBatch, ChangeFinding
from app.workflows.steps import STEP_TIMEOUT_SECONDS, solve

Mode = Literal["clause", "obligation"]
ChangeKind = Literal["modified", "added", "removed", "carried_over"]

# Sub-paragraphs such as "8.2" at the start of a line.
_SUBPARAGRAPH = re.compile(r"(?m)^[ \t]*(\d{1,3}\.\d{1,2})\s")
# Where the operative text ends: a line of asterisks or the signature block.
_BODY_END = re.compile(r"(?im)^[ \t]*(\*{5,}|yours faithfully)")
# Heading of a withdrawn / repealed circulars table.
_ANNEX_HEADING = re.compile(
    r"(?im)^[^\n]*\b(circulars?|notifications?|instructions?)\b[^\n]*"
    r"\b(withdrawn|repealed|consolidated)\b[^\n]*$"
)
_ROW_START = re.compile(r"^[ \t]*(\d{1,3})(?:[ \t]+(\S.*))?$")
_NUMERIC_DATE = re.compile(r"\b(\d{2})([./-])(\d{2})\2(\d{4})\b")
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_LONG_DATE = re.compile(rf"\b({'|'.join(_MONTHS)})\s+(\d{{1,2}}),\s*(\d{{4}})\b")
_WITHDRAWAL_SENTENCE = re.compile(
    r"[^.]*\b(?:stand|are|is|shall stand)\s+(?:hereby\s+)?(?:withdrawn|repealed)\b[^.]*\.", re.I
)
_WATERMARK = re.compile(
    rf"\bWithdrawn\s+(?:from|with effect from|w\.e\.f\.?)\s+((?:{'|'.join(_MONTHS)})\s+\d{{1,2}},\s*\d{{4}})",
    re.I,
)
_HEADER_END = re.compile(r"(?i)dear\s+sir|madam|table of contents|\b1\.\s+introduction")
_HEADER_MAX_CHARS = 1500
# An Annex row matched by date also needs a subject this close to the document's title.
_SUBJECT_MATCH_RATIO = 0.85
_DUTY_WORDS = re.compile(r"\b(shall|must|required|ensure|should|mandatory|not be)\b", re.I)
_STOP_WORDS = frozenset(
    re.findall(
        r"\w+",
        "the and for of to a an in on by with at is are be as or any all this that these which "
        "shall should must may such from their its it has have been notes note banks bank",
    )
)


# ---------------------------------------------------------------- inputs and results


@dataclass(frozen=True)
class DocumentVersion:
    id: str
    title: str
    reference: str
    version_label: str
    text: str


@dataclass(frozen=True)
class CorpusDocument:
    """A document already in the corpus, matched against the Annex of withdrawn circulars."""

    id: str
    title: str
    reference: str
    version_label: str
    text: str


@dataclass(frozen=True)
class ChangeOptions:
    min_ref_share: float = 0.6
    min_heading_similarity: float = 0.6
    max_units: int = 60


# Defaults for tests; the runner passes the values from Settings.
DEFAULT_OPTIONS = ChangeOptions()


@dataclass(frozen=True)
class DetectedChange:
    kind: ChangeKind
    old_ref: str | None
    new_ref: str | None
    old_text: str | None
    new_text: str | None
    title: str
    summary: str
    significance: str
    carried_from: str | None = None
    problems: tuple[str, ...] = ()

    @property
    def verdict(self) -> Verdict:
        return verdict_for(self.problems)


@dataclass(frozen=True)
class AnnexRow:
    row: int
    reference: str
    date: str  # as printed, e.g. "24.04.2025"
    subject: str

    @property
    def display_date(self) -> str:
        parsed = parse_date(self.date)
        return (
            f"{parsed.day} {_MONTHS[parsed.month - 1][:3]} {parsed.year}" if parsed else self.date
        )


@dataclass(frozen=True)
class AnnexMatch:
    row: AnnexRow
    document_ids: tuple[str, ...]

    @property
    def in_corpus(self) -> bool:
        return bool(self.document_ids)


@dataclass
class ChangeReport:
    mode: Mode
    mode_reason: str
    changes: list[DetectedChange] = field(default_factory=list)
    annex: list[AnnexMatch] = field(default_factory=list)
    withdrawal_sentence: str | None = None
    issue_date: str | None = None
    circular_number: str | None = None
    unresolved: list[str] = field(default_factory=list)
    llm_calls: int = 0
    error: str | None = None


# ---------------------------------------------------------------- units


def _trim_body(text: str) -> str:
    match = _BODY_END.search(text)
    return text[: match.start()].rstrip() if match else text.rstrip()


def _split_subparagraphs(paragraph: Paragraph) -> list[Paragraph]:
    """'8.' with '8.1' and '8.2' inside becomes two units, so a change is pinned to 8.2."""
    marks = [
        m
        for m in _SUBPARAGRAPH.finditer(paragraph.text)
        if m.group(1).split(".")[0] == paragraph.ref
    ]
    if not marks:
        return [paragraph]
    units: list[Paragraph] = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(paragraph.text)
        units.append(Paragraph(ref=mark.group(1), text=paragraph.text[mark.start() : end].strip()))
    return units


def document_units(text: str) -> list[Paragraph]:
    """Numbered units of a document, split to sub-paragraphs, with signature blocks, formats and
    Annexes removed from the last paragraph. The tail after the operative text (e.g. a testing
    procedure) is kept as one extra unit when it states a duty."""
    annex = _annex_heading(text)
    body = text[: annex.start()] if annex and parse_annex(text) else text
    units: list[Paragraph] = []
    for paragraph in split_paragraphs(body):
        trimmed = Paragraph(ref=paragraph.ref, text=_trim_body(paragraph.text))
        units.extend(_split_subparagraphs(trimmed))
        tail_match = _BODY_END.search(paragraph.text)
        if tail_match and tail_match.group(1).startswith("*"):
            tail = paragraph.text[tail_match.end() :].strip()
            # Drop a dangling "Annex" heading left over from the table removed above.
            tail = re.sub(r"(?i)\n\s*annex(ure)?\s*$", "", tail).strip()
            if _DUTY_WORDS.search(tail):
                heading = next(
                    (ln.strip() for ln in tail.splitlines() if re.search(r"[A-Za-z]{4}", ln)),
                    "Appendix",
                )
                units.append(Paragraph(ref=heading[:48], text=tail))
    return units


def _heading(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else ""
    return normalise(re.sub(r"^\s*\d{1,3}[A-Z]?\.\s*", "", first)).lower()[:120]


# ---------------------------------------------------------------- mode


def choose_mode(
    old: Sequence[Paragraph],
    new: Sequence[Paragraph],
    options: ChangeOptions = DEFAULT_OPTIONS,
) -> tuple[Mode, str]:
    """Same structure -> 'clause' (diff by paragraph number); otherwise 'obligation'."""
    old_by_ref = {p.ref: p for p in old}
    new_by_ref = {p.ref: p for p in new}
    shared = [ref for ref in new_by_ref if ref in old_by_ref]
    larger = max(len(old_by_ref), len(new_by_ref), 1)
    ref_share = len(shared) / larger
    heading = (
        sum(
            difflib.SequenceMatcher(
                a=_heading(old_by_ref[r].text), b=_heading(new_by_ref[r].text), autojunk=False
            ).ratio()
            for r in shared
        )
        / len(shared)
        if shared
        else 0.0
    )
    reason = (
        f"{len(shared)} of {larger} paragraph numbers shared ({ref_share:.0%}), "
        f"heading similarity {heading:.0%}"
    )
    if ref_share >= options.min_ref_share and heading >= options.min_heading_similarity:
        return "clause", reason
    return "obligation", reason


# ---------------------------------------------------------------- mode (a): clause diff


def _same(a: str, b: str) -> bool:
    return normalise(a) == normalise(b)


def diff_units(
    old: Sequence[Paragraph], new: Sequence[Paragraph]
) -> list[tuple[ChangeKind, str | None, str | None]]:
    """(kind, old_ref, new_ref) for every unit that differs beyond whitespace."""
    old_by_ref = {p.ref: p for p in old}
    new_by_ref = {p.ref: p for p in new}
    found: list[tuple[ChangeKind, str | None, str | None]] = []
    for paragraph in new:
        before = old_by_ref.get(paragraph.ref)
        if before is None:
            found.append(("added", None, paragraph.ref))
        elif not _same(before.text, paragraph.text):
            found.append(("modified", paragraph.ref, paragraph.ref))
    found.extend(("removed", p.ref, None) for p in old if p.ref not in new_by_ref)
    return found


def _diff_summary(old_text: str | None, new_text: str | None) -> str:
    """Plain description of a text change, used when no verified model summary is available."""
    if old_text is None:
        return "New paragraph in the later version."
    if new_text is None:
        return "Paragraph no longer present in the later version."
    a, b = normalise(old_text).split(), normalise(new_text).split()
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            parts.append(f"removed '{' '.join(a[i1:i2])[:120]}'")
        if tag in ("replace", "insert"):
            parts.append(f"added '{' '.join(b[j1:j2])[:120]}'")
    return ("Text changed: " + "; ".join(parts[:4]) + ".") if parts else "Text changed."


# ---------------------------------------------------------------- mode (b): obligation match


def _terms(text: str) -> set[str]:
    words = {w.lower().strip(".,;:()'\"‘’“”/-") for w in normalise(text).split()}
    return {w for w in words if len(w) > 2 and w not in _STOP_WORDS and not w.isdigit()}


def common_terms(units: Sequence[Paragraph], share: float = 0.4) -> frozenset[str]:
    """Words found in at least ``share`` of all units (e.g. 'reserve', 'machines'): they say
    nothing about which duty a unit is about, so they are not used to pair units."""
    counts: dict[str, int] = {}
    for unit in units:
        for term in _terms(unit.text):
            counts[term] = counts.get(term, 0) + 1
    floor = max(2, int(len(units) * share))
    return frozenset(t for t, n in counts.items() if n >= floor)


def candidate_counterparts(
    unit: Paragraph,
    others: Sequence[Paragraph],
    *,
    common: frozenset[str] = frozenset(),
    limit: int = 3,
) -> list[tuple[str, list[str]]]:
    """Units of the other version that share at least two topic words, best first. These are
    hints for the model, which may still match a different unit or none."""
    own = _terms(unit.text) - common
    scored: list[tuple[int, str, list[str]]] = []
    for other in others:
        shared = sorted(own & _terms(other.text))
        if len(shared) >= 2:
            scored.append((len(shared), other.ref, shared))
    scored.sort(key=lambda item: -item[0])
    return [(ref, shared[:6]) for _, ref, shared in scored[:limit]]


# ---------------------------------------------------------------- model step


def _states_duty(unit: Paragraph) -> bool:
    return bool(_DUTY_WORDS.search(unit.text))


def _label_units(
    provider: StructuredLLMProvider,
    *,
    old: DocumentVersion,
    new: DocumentVersion,
    units: Mapping[str, str],
    tasks: Mapping[str, str],
    expected: Mapping[str, str],
) -> tuple[dict[str, tuple[ChangeFinding | None, tuple[str, ...]]], int]:
    """Runs generate -> check -> retry once -> flag over the units in ``tasks``."""

    def call(
        keys: list[str], notes: Mapping[str, tuple[str, ...]]
    ) -> Iterable[tuple[str, ChangeFinding]]:
        prompt = prompts.change_prompt(
            old_label=f"{old.title} · {old.version_label}",
            new_label=f"{new.title} · {new.version_label}",
            sources=units,
            tasks=[tasks[k] for k in keys],
            notes=notes,
        )
        response = provider.generate_structured(
            prompt=prompt, schema=ChangeBatch, timeout_seconds=STEP_TIMEOUT_SECONDS
        )
        return [(f.unit.strip(), f) for f in response.findings]

    def check(key: str, finding: ChangeFinding) -> tuple[str, ...]:
        return check_change(
            finding,
            unit=key,
            units=units,
            new_full_text=new.text,
            expected_label=expected.get(key),
        )

    settled, calls = solve(list(tasks), call=call, check=check)
    results: dict[str, tuple[ChangeFinding | None, tuple[str, ...]]] = {}
    for item in settled:
        # Keep the first answer per unit; a unit answered twice keeps the earlier one.
        results.setdefault(item.key, (item.draft, item.problems))
    return results, calls


def _strip_id(unit: str) -> str:
    return unit.split(" ", 1)[1] if " " in unit else unit


# ---------------------------------------------------------------- annex


def parse_date(value: str) -> date | None:
    numeric = _NUMERIC_DATE.search(value)
    try:
        if numeric:
            return date(int(numeric.group(4)), int(numeric.group(3)), int(numeric.group(1)))
        long = _LONG_DATE.search(value)
        if long:
            return date(int(long.group(3)), _MONTHS.index(long.group(1)) + 1, int(long.group(2)))
    except ValueError:
        return None
    return None


def _annex_heading(text: str) -> re.Match[str] | None:
    """The last "circulars withdrawn" heading: earlier matches are covering-letter sentences."""
    heading = None
    for heading in _ANNEX_HEADING.finditer(text):  # noqa: B007 - keep the last match
        pass
    return heading


def _join_wrapped(lines: Sequence[str]) -> str:
    """Joins PDF lines. A line that ends in a space was a word break; one that does not is a
    token wrapped mid-way (e.g. 'No.S488/18.' + '00.14/2022-23'), so it is joined directly."""
    return normalise("".join(line.lstrip() for line in lines))


def _first_date(text: str) -> re.Match[str] | None:
    for match in _NUMERIC_DATE.finditer(text):
        if parse_date(match.group(0)):
            return match
    return _LONG_DATE.search(text)


def parse_annex(text: str) -> list[AnnexRow]:
    """Rows of the "List of Circulars withdrawn" (or repealed) table at the end of a direction.

    A row starts with its serial number (1, 2, 3 ... in order) at the start of a line; its
    reference runs up to the first date, and the subject follows the date.
    """
    heading = _annex_heading(text)
    if heading is None:
        return []
    rows: list[tuple[int, list[str]]] = []
    for line in text[heading.end() :].splitlines():
        start = _ROW_START.match(line)
        expected = rows[-1][0] + 1 if rows else 1
        if start and int(start.group(1)) == expected:
            rows.append((expected, [start.group(2)] if start.group(2) else []))
        elif rows and line.strip():
            rows[-1][1].append(line)

    parsed: list[AnnexRow] = []
    for number, row_lines in rows:
        raw = "\n".join(row_lines)
        found = _first_date(raw)
        if found is None:
            continue
        before = raw[: found.start()].splitlines()
        after = raw[found.end() :].splitlines()
        # Keep each line's trailing space so wrapped tokens can be told from word breaks.
        reference = _join_wrapped([ln for ln in before if ln.strip()] or [""])
        subject = normalise(" ".join(after))
        if reference:
            parsed.append(
                AnnexRow(row=number, reference=reference, date=found.group(0), subject=subject)
            )
    return parsed


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def document_header(text: str) -> str:
    """The letterhead part of a circular: reference number, date, addressee."""
    head = text[: _HEADER_MAX_CHARS * 2]
    end = _HEADER_END.search(head)
    return head[: end.start()] if end else head[:_HEADER_MAX_CHARS]


def _date_forms(value: date) -> set[str]:
    month = _MONTHS[value.month - 1]
    return {
        _compact(f"{month} {value.day:02d}, {value.year}"),
        _compact(f"{month} {value.day}, {value.year}"),
        _compact(f"{value.day} {month[:3]} {value.year}"),
        _compact(f"{value.day} {month} {value.year}"),
        _compact(value.isoformat()),
    }


def match_annex(rows: Sequence[AnnexRow], corpus: Sequence[CorpusDocument]) -> list[AnnexMatch]:
    """Finds each withdrawn circular in the corpus. A document matches by its circular reference
    (in its reference field or its letterhead), or by date plus a subject close to its title.
    Only the letterhead is used: the body of a circular often cites earlier circulars."""
    identities = [
        (
            doc,
            _compact(
                f"{doc.reference} {doc.title} {doc.version_label} {document_header(doc.text)}"
            ),
        )
        for doc in corpus
    ]
    matches: list[AnnexMatch] = []
    for row in rows:
        key = _compact(row.reference)
        when = parse_date(row.date)
        found: list[str] = []
        for doc, identity in identities:
            by_reference = bool(key) and key in identity
            by_date = (
                when is not None
                and any(form in identity for form in _date_forms(when))
                and difflib.SequenceMatcher(
                    a=_compact(row.subject), b=_compact(doc.title), autojunk=False
                ).ratio()
                >= _SUBJECT_MATCH_RATIO
            )
            if by_reference or by_date:
                found.append(doc.id)
        matches.append(AnnexMatch(row=row, document_ids=tuple(found)))
    return matches


def withdrawal_watermark(text: str) -> str | None:
    """'October 02, 2026' when the document is stamped 'Withdrawn from October 02, 2026'."""
    match = _WATERMARK.search(text)
    return normalise(match.group(1)) if match else None


def _circular_number(header: str) -> str | None:
    for line in header.splitlines():
        if re.search(r"\bNo\.\s*\S", line):
            return normalise(re.split(r"\s{2,}", line.strip())[0])
    return None


def annex_row_for(text: str, matches: Sequence[AnnexMatch]) -> AnnexMatch | None:
    """The Annex row whose reference appears in ``text`` (e.g. a carried-over source)."""
    compact = _compact(text)
    return next((m for m in matches if _compact(m.row.reference) in compact), None)


# ---------------------------------------------------------------- entry point


def detect_changes(
    provider: StructuredLLMProvider | None,
    *,
    old: DocumentVersion,
    new: DocumentVersion,
    corpus: Sequence[CorpusDocument] = (),
    options: ChangeOptions = DEFAULT_OPTIONS,
) -> ChangeReport:
    """Compares two versions. Without a provider (or if the call fails) the deterministic parts
    still run: clause diffs are kept and flagged for review, and the Annex is still parsed."""
    old_units = document_units(old.text)[: options.max_units]
    new_units = document_units(new.text)[: options.max_units]
    mode, reason = choose_mode(split_paragraphs(old.text), split_paragraphs(new.text), options)
    header = document_header(new.text)
    issued = _LONG_DATE.search(header)
    sentence = _WITHDRAWAL_SENTENCE.search(normalise(new.text[: _HEADER_MAX_CHARS * 3]))
    report = ChangeReport(
        mode=mode,
        mode_reason=reason,
        annex=match_annex(parse_annex(new.text), [d for d in corpus if d.id != new.id]),
        withdrawal_sentence=sentence.group(0).strip() if sentence else None,
        issue_date=normalise(issued.group(0)) if issued else None,
        circular_number=_circular_number(header),
    )
    if not old_units or not new_units:
        report.error = "One of the versions has no readable numbered paragraphs."
        return report

    all_units = {f"old {p.ref}": p.text for p in old_units} | {
        f"new {p.ref}": p.text for p in new_units
    }
    tasks: dict[str, str] = {}
    expected: dict[str, str] = {}
    if mode == "clause":
        for kind, old_ref, new_ref in diff_units(old_units, new_units):
            key = f"new {new_ref}" if new_ref else f"old {old_ref}"
            expected[key] = kind
            hint = f" (counterpart: old {old_ref})" if kind == "modified" else ""
            tasks[key] = f"{key}: label {kind}{hint}"
        # Only the changed paragraphs are sent, on both sides.
        refs = {_strip_id(k) for k in tasks}
        units = {k: v for k, v in all_units.items() if _strip_id(k) in refs}
    else:
        units = all_units
        common = common_terms([*old_units, *new_units])
        sides = (("new", new_units, old_units, "old"), ("old", old_units, new_units, "new"))
        for side, own, others, other_side in sides:
            for unit in own:
                if not _states_duty(unit):
                    continue
                hints = candidate_counterparts(unit, others, common=common)
                hint = "; ".join(f"{other_side} {ref} (shared: {', '.join(t)})" for ref, t in hints)
                tasks[f"{side} {unit.ref}"] = f"{side} {unit.ref}" + (
                    f" - possible counterparts: {hint}" if hint else ""
                )
    if not tasks:
        return report

    results: dict[str, tuple[ChangeFinding | None, tuple[str, ...]]]
    if provider is None:
        results = {k: (None, ("no language model is configured",)) for k in tasks}
    else:
        try:
            results, report.llm_calls = _label_units(
                provider, old=old, new=new, units=units, tasks=tasks, expected=expected
            )
        except LLMProviderError as exc:
            report.error = str(exc)
            report.llm_calls = 1
            results = {k: (None, (f"model call failed: {exc}",)) for k in tasks}

    if mode == "clause":
        report.changes = _assemble_clause(results, units, expected)
    else:
        report.changes, report.unresolved = _assemble_obligation(results, units)
    return report


def _assemble_clause(
    results: Mapping[str, tuple[ChangeFinding | None, tuple[str, ...]]],
    units: Mapping[str, str],
    expected: Mapping[str, str],
) -> list[DetectedChange]:
    """In clause mode the text diff decides the kind; the model only explains it. An unverified
    or missing explanation keeps the diff, with a plain summary, flagged for review."""
    changes: list[DetectedChange] = []
    for key, (finding, problems) in results.items():
        ref = _strip_id(key)
        kind = cast("ChangeKind", expected[key])
        old_ref = ref if kind != "added" else None
        new_ref = ref if kind != "removed" else None
        old_text = units.get(f"old {old_ref}") if old_ref else None
        new_text = units.get(f"new {new_ref}") if new_ref else None
        explained = finding if finding is not None and not problems else None
        title = finding.title.strip() if finding is not None else ""
        changes.append(
            DetectedChange(
                kind=kind,
                old_ref=old_ref,
                new_ref=new_ref,
                old_text=old_text,
                new_text=new_text,
                title=title or f"Paragraph {ref} {kind}",
                summary=explained.summary.strip()
                if explained
                else _diff_summary(old_text, new_text),
                significance=explained.significance if explained else "medium",
                problems=problems,
            )
        )
    return changes


def _assemble_obligation(
    results: Mapping[str, tuple[ChangeFinding | None, tuple[str, ...]]],
    units: Mapping[str, str],
) -> tuple[list[DetectedChange], list[str]]:
    """Turns per-unit findings into changes. A modified pair is reported once; when the new side
    called a unit 'added' but the old side matched it, the pair becomes one modification."""
    by_new: dict[str, DetectedChange] = {}
    others: list[DetectedChange] = []
    unresolved: list[str] = []
    # New-side findings first.
    for key in sorted(results, key=lambda k: (not k.startswith("new "), k)):
        finding, problems = results[key]
        side, ref = key.split(" ", 1)
        if finding is None:
            unresolved.append(key)
            continue
        if finding.label in ("unchanged", "no_obligation"):
            continue
        counterpart = finding.counterpart.strip()
        kind = finding.label
        old_ref: str | None
        new_ref: str | None
        if kind == "modified":
            other_ref = _strip_id(counterpart) if counterpart in units else None
            old_ref, new_ref = (ref, other_ref) if side == "old" else (other_ref, ref)
        elif kind == "removed" and side == "old":
            old_ref, new_ref = ref, None
        elif kind in ("added", "carried_over") and side == "new":
            old_ref, new_ref = None, ref
        else:
            unresolved.append(key)
            continue
        change = DetectedChange(
            kind=kind,
            old_ref=old_ref,
            new_ref=new_ref,
            old_text=units.get(f"old {old_ref}") if old_ref else None,
            new_text=units.get(f"new {new_ref}") if new_ref else None,
            title=finding.title.strip() or f"Paragraph {ref} {kind}",
            summary=finding.summary.strip(),
            significance=finding.significance,
            carried_from=finding.carried_from.strip() or None,
            problems=problems,
        )
        if side == "new":
            by_new[ref] = change
            continue
        existing = by_new.get(new_ref) if new_ref else None
        if kind == "modified" and existing is not None:
            if existing.kind == "added" and new_ref is not None:
                by_new[new_ref] = replace(change, problems=change.problems + existing.problems)
            # A pair the new side already reported is not repeated.
            continue
        others.append(change)
    return [*by_new.values(), *others], [_strip_id(k) for k in unresolved]
