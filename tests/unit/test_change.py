"""Change intelligence: mode choice, clause diff, Annex parsing and critic flagging (no network)."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.services.change_runner import CHANGE_NODE, _Obligation, obligations_at
from app.services.pipeline_runner import _node_rows, _Totals
from app.services.regulation_text import Paragraph, extract_text, split_paragraphs
from app.workflows.change import (
    ChangeOptions,
    CorpusDocument,
    DocumentVersion,
    choose_mode,
    detect_changes,
    diff_units,
    document_units,
    match_annex,
    parse_annex,
    withdrawal_watermark,
)
from app.workflows.critic import Verdict
from app.workflows.pipeline import AgentRun as NodeRecord
from tests.unit.test_pipeline import ScriptedProvider

# Shaped like the real NSM v1 circular: unnumbered opening, then paragraphs 2 and 3.
OLD_CIRCULAR = (
    "RESERVE BANK OF INDIA\n"
    "RBI/2024-2025/86\n"
    "DCM (NPD) No.S2193/09.45.000/2024-25           October 30, 2024\n"
    "Madam / Dear Sir,\n"
    "Note Sorting Machines: Standards issued by the Bureau of Indian Standards\n"
    "Reference is invited to our circular DCM (NPD) No. S488/18.00.14/2022-23 dated "
    "July 01, 2022.\n"
    "2. The Bureau of Indian Standards published the standards for Note Sorting Machines.\n"
    "3. As a step further, it has been decided that effective May 01, 2025, banks\n"
    "should deploy only such NSM models that conform to the aforesaid Indian Standards and are\n"
    "duly certified by BIS.\n"
    "Yours faithfully\n"
    "Withdrawn from October 02, 2026\n"
)

# Shaped like the real NSM v2 Master Direction, including the PDF line breaks in the Annex.
NEW_DIRECTION = (
    "RESERVE BANK OF INDIA\n"
    "DCM(NPD) No.S2154/18.00.014/2026-27                    October 02, 2026\n"
    "Madam / Dear Sir,\n"
    "The previous circulars issued on the subject (Annexed) stand withdrawn from the date of "
    "issuance of this Master Direction.\n"
    "1. Introduction\n"
    "Revised guidelines were issued to banks vide circular DCM (NPD)No. \n"
    "S488/18.00.14/2022-23 dated July 01, 2022.\n"
    "2. Authenticity Check\n"
    "The machines shall perform authenticity check with reference to the features of genuine "
    "notes.\n"
    "3. Standards issued by the Bureau of Indian Standards\n"
    "3.1 The Bureau of Indian Standards published the standards for Note Sorting Machines.\n"
    "3.2 NSM models deployed at banks which have been discontinued from production, \n"
    "shall be phased out on or before June 30, 2027. Going forward, banks shall only procure "
    "the BIS certified Note Sorting Machines (NSMs).\n"
    "***************************\n"
    " Annex \n"
    "List of Circulars withdrawn \n"
    "Sr. \n"
    "No. \n"
    "Circular / Notification \n"
    "No. Date Subject \n"
    "1 DCM(NPD)No.S488/18.\n"
    "00.14/2022-23 \n"
    "01.07.2022 Note Sorting Machines - \n"
    "Authentication and Fitness Sorting \n"
    "Parameters \n"
    "2 DCM (NPD) \n"
    "No.S2193/09.45.000/20\n"
    "24-25 \n"
    "30.10.2024 Note Sorting Machines: Standards \n"
    "issued by the Bureau of Indian \n"
    "Standards \n"
    "3 DCM (NPD) \n"
    "No.S287/18.00.014/202\n"
    "5-26 \n"
    "24.04.2025 Note Sorting Machines: Standards \n"
    "issued by the Bureau of Indian \n"
    "Standards - Revised Timeline for \n"
    "Implementation \n"
)

OLD = DocumentVersion("doc-v1", "NSM circular", "NSM_v1.pdf", "v1", OLD_CIRCULAR)
NEW = DocumentVersion("doc-v2", "NSM Master Direction", "NSM_v2.pdf", "v2", NEW_DIRECTION)
CORPUS = [
    CorpusDocument(
        "doc-v1",
        "Note Sorting Machines: Standards issued by the Bureau of Indian Standards",
        "NSM_v1.pdf",
        "v1",
        OLD_CIRCULAR,
    ),
    CorpusDocument("doc-v2", "NSM Master Direction", "NSM_v2.pdf", "v2", NEW_DIRECTION),
]


def _finding(unit: str, label: str, **values: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "unit": unit,
        "label": label,
        "title": f"{unit} {label}",
        "summary": f"{unit} is {label}.",
        "significance": "medium",
    }
    base.update(values)
    return base


MODIFIED_NEW = _finding(
    "new 3.2",
    "modified",
    counterpart="old 3",
    significance="high",
    old_quote="banks should deploy only such NSM models",
    new_quote="shall be phased out on or before June 30, 2027.",
)
MODIFIED_OLD = {**MODIFIED_NEW, "unit": "old 3", "counterpart": "new 3.2"}
CARRIED = _finding(
    "new 2",
    "carried_over",
    significance="low",
    new_quote="The machines shall perform authenticity check",
    carried_from="DCM (NPD)No. S488/18.00.14/2022-23 dated July 01, 2022",
)


def _scripted(*responses: list[dict[str, Any]]) -> ScriptedProvider:
    calls = iter(responses)

    def respond(prompt: str) -> dict[str, Any]:
        return {"findings": next(calls)}

    responders: dict[str, Callable[[str], Any]] = {"ChangeBatch": respond}
    return ScriptedProvider(responders)


# ---------------------------------------------------------------- mode


def test_circular_to_master_direction_uses_obligation_mode() -> None:
    mode, reason = choose_mode(split_paragraphs(OLD_CIRCULAR), split_paragraphs(NEW_DIRECTION))

    # Paragraph numbers 1-3 exist in both, but the headings say they are different paragraphs.
    assert mode == "obligation"
    assert "heading similarity" in reason


def test_revised_direction_with_same_numbering_uses_clause_mode() -> None:
    old = [Paragraph(str(n), f"{n}. Heading {n}\nBody text {n}.") for n in range(1, 6)]
    new = [Paragraph(str(n), f"{n}. Heading {n}\nBody text {n} revised.") for n in range(1, 6)]

    assert choose_mode(old, new)[0] == "clause"
    assert choose_mode(old, new[:2], ChangeOptions(min_ref_share=0.6))[0] == "obligation"


# ---------------------------------------------------------------- mode (a)

OLD_SAME = (
    "1. Scope\nThese directions apply to all banks.\n"
    "2. Records\nBanks shall keep records for five years.\n"
    "3. Review\nBanks shall review the policy annually.\n"
    "4. Reporting\nBanks shall report monthly.\n"
)
NEW_SAME = (
    "1. Scope\nThese  directions apply\n to all banks.\n"  # whitespace only
    "2. Records\nBanks shall keep records for eight years.\n"
    "3. Review\nBanks shall review the policy annually.\n"
    "5. Training\nBanks shall train staff every year.\n"
)


def test_clause_diff_ignores_whitespace_and_classifies_changes() -> None:
    found = diff_units(split_paragraphs(OLD_SAME), split_paragraphs(NEW_SAME))

    assert found == [("modified", "2", "2"), ("added", None, "5"), ("removed", "4", None)]


def test_clause_mode_uses_one_call_and_keeps_diff_kinds() -> None:
    provider = _scripted(
        [
            _finding(
                "new 2",
                "modified",
                counterpart="old 2",
                significance="high",
                old_quote="keep records for five years",
                new_quote="keep records for eight years",
            ),
            _finding("new 5", "added", new_quote="Banks shall train staff every year."),
            _finding("old 4", "removed", old_quote="Banks shall report monthly."),
        ]
    )
    old = DocumentVersion("a", "Direction", "", "2025", OLD_SAME)
    new = DocumentVersion("b", "Direction", "", "2026", NEW_SAME)

    report = detect_changes(provider, old=old, new=new)

    assert report.mode == "clause"
    assert report.llm_calls == 1
    kinds = {(c.kind, c.old_ref, c.new_ref, c.verdict) for c in report.changes}
    assert kinds == {
        ("modified", "2", "2", Verdict.ACCEPTED),
        ("added", None, "5", Verdict.ACCEPTED),
        ("removed", "4", None, Verdict.ACCEPTED),
    }
    # Only the changed paragraphs are sent to the model.
    assert "Scope" not in provider.prompts[0]


def test_clause_mode_without_model_keeps_diff_flagged_for_review() -> None:
    old = DocumentVersion("a", "Direction", "", "2025", OLD_SAME)
    new = DocumentVersion("b", "Direction", "", "2026", NEW_SAME)

    report = detect_changes(None, old=old, new=new)

    assert len(report.changes) == 3
    assert all(c.verdict == Verdict.NEEDS_REVIEW for c in report.changes)
    modified = next(c for c in report.changes if c.kind == "modified")
    assert "eight" in modified.summary


# ---------------------------------------------------------------- mode (b) and the critic


def test_obligation_mode_reports_modified_pair_once_and_carried_over() -> None:
    provider = _scripted([MODIFIED_NEW, MODIFIED_OLD, CARRIED])

    report = detect_changes(provider, old=OLD, new=NEW, corpus=CORPUS)

    assert report.llm_calls == 1
    by_kind = {c.kind: c for c in report.changes}
    assert set(by_kind) == {"modified", "carried_over"}
    modified = by_kind["modified"]
    assert (modified.old_ref, modified.new_ref) == ("3", "3.2")
    assert modified.verdict == Verdict.ACCEPTED
    assert modified.old_text and "Yours faithfully" not in modified.old_text
    assert by_kind["carried_over"].carried_from
    # The model saw both versions, wrapped as untrusted source text.
    assert '<source id="old 3">' in provider.prompts[0]
    assert '<source id="new 3.2">' in provider.prompts[0]


def test_unverifiable_quote_is_retried_once_then_flagged() -> None:
    paraphrased = {**MODIFIED_NEW, "new_quote": "must be phased out by June 2027"}
    provider = _scripted([paraphrased, MODIFIED_OLD, CARRIED], [paraphrased])

    report = detect_changes(provider, old=OLD, new=NEW, corpus=CORPUS)

    assert report.llm_calls == 2
    assert "Your previous answer" in provider.prompts[1]
    flagged = [c for c in report.changes if c.verdict == Verdict.NEEDS_REVIEW]
    assert len(flagged) == 1
    assert any("new_quote" in p for p in flagged[0].problems)


def test_retry_that_fixes_the_quote_is_accepted() -> None:
    paraphrased = {**MODIFIED_NEW, "new_quote": "must be phased out by June 2027"}
    provider = _scripted([paraphrased, MODIFIED_OLD, CARRIED], [MODIFIED_NEW])

    report = detect_changes(provider, old=OLD, new=NEW, corpus=CORPUS)

    assert report.llm_calls == 2
    assert all(c.verdict == Verdict.ACCEPTED for c in report.changes)


def test_carried_over_claim_needs_a_source_named_in_the_new_text() -> None:
    invented = {**CARRIED, "carried_from": "circular dated 01.01.2020"}
    provider = _scripted([MODIFIED_NEW, MODIFIED_OLD, invented], [invented])

    report = detect_changes(provider, old=OLD, new=NEW, corpus=CORPUS)

    carried = next(c for c in report.changes if c.kind == "carried_over")
    assert carried.verdict == Verdict.NEEDS_REVIEW


# ---------------------------------------------------------------- annex


def test_annex_rows_are_parsed_from_wrapped_pdf_lines() -> None:
    rows = parse_annex(NEW_DIRECTION)

    assert [r.row for r in rows] == [1, 2, 3]
    assert rows[0].reference == "DCM(NPD)No.S488/18.00.14/2022-23"
    assert rows[1].reference == "DCM (NPD) No.S2193/09.45.000/2024-25"
    assert rows[2].display_date == "24 Apr 2025"
    assert rows[2].subject.endswith("Revised Timeline for Implementation")


def test_annex_rows_match_the_corpus_by_letterhead_only() -> None:
    matches = match_annex(parse_annex(NEW_DIRECTION), CORPUS[:1])

    # Row 2 is the old circular. Row 1 is only cited in that circular's body, so it is missing.
    assert [m.document_ids for m in matches] == [(), ("doc-v1",), ()]
    report = detect_changes(None, old=OLD, new=NEW, corpus=CORPUS)
    missing = [m.row.display_date for m in report.annex if not m.in_corpus]
    assert missing == ["1 Jul 2022", "24 Apr 2025"]
    assert report.withdrawal_sentence and "stand withdrawn" in report.withdrawal_sentence
    assert report.circular_number == "DCM(NPD) No.S2154/18.00.014/2026-27"
    assert withdrawal_watermark(OLD_CIRCULAR) == "October 02, 2026"


def test_annex_table_is_not_part_of_the_last_paragraph() -> None:
    units = {u.ref: u.text for u in document_units(NEW_DIRECTION)}

    assert set(units) == {"1", "2", "3.1", "3.2"}
    assert "Circulars withdrawn" not in units["3.2"]
    assert "*****" not in units["3.2"]


REAL_V2 = Path("demo_data/1_regulations_rbi/NSM_v2_RBI_Master_Direction_2026-10-02.pdf")


@pytest.mark.skipif(not REAL_V2.is_file(), reason="real NSM v2 PDF not available")
def test_real_nsm_v2_annex_lists_five_withdrawn_circulars() -> None:
    text = extract_text(REAL_V2.read_bytes(), REAL_V2.name)

    rows = parse_annex(text)

    assert len(rows) == 5
    assert rows[3].reference == "DCM (NPD) No.S2193/09.45.000/2024-25"
    assert (rows[4].date, rows[4].display_date) == ("24.04.2025", "24 Apr 2025")
    assert "Revised Timeline for Implementation" in rows[4].subject
    refs = [u.ref for u in document_units(text)]
    assert "8.2" in refs and "Quarterly Test Reporting Format" in refs


# ---------------------------------------------------------------- impact and run nodes


def test_obligations_at_matches_sub_clause_by_quote() -> None:
    obligations = [
        _Obligation(
            "o1", "OB-01", "8", "shall be phased out on or before June 30, 2027", "nsm", "a"
        ),
        _Obligation("o2", "OB-02", "7", "tested for accuracy", "nsm", "a"),
        _Obligation("o3", "OB-03", "para 8.2", "something else", "nsm", "a"),
    ]
    unit = "8.2 NSM models ... shall be phased out on or before June 30, 2027."

    assert [o.code for o in obligations_at(obligations, "8.2", unit)] == ["OB-01", "OB-03"]
    assert obligations_at(obligations, None, unit) == []


def test_change_node_is_listed_as_conditional() -> None:
    start = datetime(2026, 10, 11, tzinfo=UTC)
    totals = _Totals()
    totals.record(
        NodeRecord(
            node=CHANGE_NODE,
            status="ok",
            started_at=start,
            ended_at=start,
            llm_calls=1,
        ),
        "NSM: obligation mode",
    )

    rows = _node_rows(totals, start, None)

    assert [r["node"] for r in rows][-1] == CHANGE_NODE
    assert [r["conditional"] for r in rows] == [False, False, False, True]
    assert rows[-1]["note"] == "NSM: obligation mode"
    assert len(_node_rows(_Totals(), start, None)) == 3
    assert _node_rows(_Totals(), start, None, with_change=True)[-1]["conditional"] is True
