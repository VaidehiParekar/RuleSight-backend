"""Deterministic checks on model output. A schema match alone does not make an answer correct.

The critic never calls a model. It verifies that quotes are real, that codes exist, and that the
answer follows the rules. Anything it cannot verify is sent back once, then flagged for review.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.workflows.schemas import NOT_SPECIFIED, ChangeFinding, ControlJudgement, ObligationDraft

# Map typographic characters to plain ASCII so a quote still matches after copy and paste.
_CHAR_FIXES = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        " ": " ",
    }
)

MAX_REVIEW_QUOTE_CHARS = 1200


class Verdict(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"


def normalise(text: str) -> str:
    """Collapses whitespace and maps typographic characters so quotes compare reliably."""
    return " ".join(text.translate(_CHAR_FIXES).split())


def quote_in(quote: str, source: str) -> bool:
    """True only if the quote's words appear in the source, in the same order.

    Whitespace, typographic quotes and capitalisation are ignored, so a model that changes only
    the first letter is not penalised. Any change to the words themselves is caught.
    """
    needle = normalise(quote).lower()
    return bool(needle) and needle in normalise(source).lower()


@dataclass(frozen=True)
class ObligationCheck:
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def check_obligation(draft: ObligationDraft, clause_texts: Mapping[str, str]) -> ObligationCheck:
    problems: list[str] = []
    source = clause_texts.get(draft.clause_ref)
    if source is None:
        problems.append(f"clause_ref '{draft.clause_ref}' is not one of the supplied clauses")
    elif not quote_in(draft.source_quote, source):
        problems.append("source_quote is not an exact copy of the text of that clause")
    if len(draft.source_quote) > MAX_REVIEW_QUOTE_CHARS:
        problems.append("source_quote is too long; quote only the sentence that creates the duty")
    if draft.applicability == "not_applicable" and draft.applicability_reason in (
        "",
        NOT_SPECIFIED,
    ):
        problems.append("applicability_reason is required when the obligation is not applicable")
    if not draft.action.strip():
        problems.append("action is empty")
    return ObligationCheck(tuple(problems))


@dataclass(frozen=True)
class JudgementCheck:
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def check_judgement(
    judgement: ControlJudgement,
    *,
    obligation_codes: frozenset[str],
    control_texts: Mapping[str, str],
) -> JudgementCheck:
    problems: list[str] = []
    if judgement.obligation_code not in obligation_codes:
        problems.append(f"unknown obligation_code '{judgement.obligation_code}'")
    control_text = control_texts.get(judgement.control_code)
    if control_text is None:
        problems.append(f"unknown control_code '{judgement.control_code}'")
    # A claim of coverage must point at the exact sentence in the control that supports it.
    if judgement.coverage in ("covered", "partial") and (
        control_text is None or not quote_in(judgement.control_quote, control_text)
    ):
        problems.append("control_quote must be an exact copy of a sentence in that control")
    if not judgement.rationale.strip():
        problems.append("rationale is empty")
    return JudgementCheck(tuple(problems))


def verdict_for(problems: tuple[str, ...]) -> Verdict:
    """Anything still failing after the allowed retry is flagged for human review, never dropped."""
    return Verdict.ACCEPTED if not problems else Verdict.NEEDS_REVIEW


# ---------------------------------------------------------------- change findings

# Labels each side of a comparison may take. An old unit cannot be "added", a new one cannot be
# "removed".
_LABELS_FOR_SIDE: dict[str, frozenset[str]] = {
    "old": frozenset({"modified", "removed", "unchanged"}),
    "new": frozenset({"modified", "added", "carried_over", "unchanged", "no_obligation"}),
}


def check_change(
    finding: ChangeFinding,
    *,
    unit: str,
    units: Mapping[str, str],
    new_full_text: str,
    expected_label: str | None = None,
) -> tuple[str, ...]:
    """Checks one change finding. ``units`` maps ids like 'old 3' / 'new 8.2' to their text.

    Every claim must rest on verbatim quotes: the old side's quote must be in the old unit, the
    new side's quote in the new unit, and a carried-over claim must name its source in words that
    appear in the new version.
    """
    problems: list[str] = []
    side = unit.split(" ", 1)[0]
    if finding.unit != unit:
        problems.append(f"unit must be '{unit}'")
    if finding.label not in _LABELS_FOR_SIDE.get(side, frozenset()):
        problems.append(f"label '{finding.label}' is not allowed for a unit of the {side} version")
    if expected_label is not None and finding.label != expected_label:
        problems.append(f"label must be '{expected_label}' (decided by the text comparison)")

    old_text: str | None = None
    new_text: str | None = None
    if finding.label in ("modified", "unchanged"):
        other = "new" if side == "old" else "old"
        counterpart = finding.counterpart.strip()
        if not counterpart.startswith(f"{other} ") or counterpart not in units:
            problems.append(f"counterpart must be the id of a unit of the {other} version")
        else:
            old_text = units[unit] if side == "old" else units[counterpart]
            new_text = units[counterpart] if side == "old" else units[unit]
        if old_text is not None and not quote_in(finding.old_quote, old_text):
            problems.append("old_quote is not an exact copy of text in the old unit")
        if new_text is not None and not quote_in(finding.new_quote, new_text):
            problems.append("new_quote is not an exact copy of text in the new unit")
    elif finding.label in ("added", "carried_over"):
        if not quote_in(finding.new_quote, units.get(unit, "")):
            problems.append("new_quote is not an exact copy of text in this unit")
        if finding.label == "carried_over" and not quote_in(finding.carried_from, new_full_text):
            problems.append(
                "carried_from must copy the words in the new version that name the earlier "
                "instruction"
            )
    elif finding.label == "removed" and not quote_in(finding.old_quote, units.get(unit, "")):
        problems.append("old_quote is not an exact copy of text in this unit")

    for name, quote in (("old_quote", finding.old_quote), ("new_quote", finding.new_quote)):
        if len(quote) > MAX_REVIEW_QUOTE_CHARS:
            problems.append(f"{name} is too long; quote only the sentence that shows the change")
    if finding.label not in ("no_obligation", "unchanged") and not finding.summary.strip():
        problems.append("summary is empty")
    return tuple(problems)
