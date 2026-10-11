from app.workflows.critic import (
    Verdict,
    check_judgement,
    check_obligation,
    normalise,
    quote_in,
    verdict_for,
)
from app.workflows.schemas import ControlJudgement, ObligationDraft


def _draft(**overrides: object) -> ObligationDraft:
    values: dict[str, object] = {
        "clause_ref": "38",
        "source_quote": "periodic updation shall be carried out at least once in every two years",
        "topic": "periodic KYC updation",
        "action": "Re-KYC high-risk customers every two years.",
    }
    values.update(overrides)
    return ObligationDraft.model_validate(values)


def test_quote_match_ignores_whitespace_and_typographic_quotes() -> None:
    source = "The  Principal Officer shall not be nominated as the ‘Designated Director’."
    assert quote_in(
        "the Principal Officer shall not be nominated as the 'Designated Director'.", source
    )


def test_quote_match_rejects_paraphrase() -> None:
    assert not quote_in(
        "KYC must be refreshed every two years",
        "shall be carried out at least once in every two years",
    )


def test_empty_quote_never_matches() -> None:
    assert not quote_in("   ", "any text")
    assert normalise("  a \n b  ") == "a b"


def test_obligation_with_exact_quote_passes() -> None:
    clause_texts = {
        "38": "Periodic updation shall be carried out at least once in every two years."
    }
    assert check_obligation(_draft(), clause_texts).ok


def test_obligation_with_paraphrased_quote_fails() -> None:
    clause_texts = {
        "38": "Periodic updation shall be carried out at least once in every two years."
    }
    check = check_obligation(_draft(source_quote="refresh KYC every two years"), clause_texts)
    assert not check.ok
    assert any("exact copy" in p for p in check.problems)


def test_unknown_clause_reference_fails() -> None:
    check = check_obligation(_draft(clause_ref="99"), {"38": "text"})
    assert any("not one of the supplied clauses" in p for p in check.problems)


def test_not_applicable_requires_reason() -> None:
    clause_texts = {
        "38": "Periodic updation shall be carried out at least once in every two years."
    }
    check = check_obligation(_draft(applicability="not_applicable"), clause_texts)
    assert any("applicability_reason is required" in p for p in check.problems)


def _judgement(**overrides: object) -> ControlJudgement:
    values: dict[str, object] = {
        "obligation_code": "OB-001",
        "control_code": "CTRL-05",
        "coverage": "covered",
        "design": "adequate",
        "rationale": "The control performs the periodic review.",
        "control_quote": "The bank re-performs KYC every three years.",
    }
    values.update(overrides)
    return ControlJudgement.model_validate(values)


def test_covered_judgement_needs_exact_control_quote() -> None:
    controls = {"CTRL-05": "The bank re-performs KYC every three years."}
    ok = check_judgement(
        _judgement(), obligation_codes=frozenset({"OB-001"}), control_texts=controls
    )
    assert ok.ok

    bad = check_judgement(
        _judgement(control_quote="The bank checks KYC often."),
        obligation_codes=frozenset({"OB-001"}),
        control_texts=controls,
    )
    assert any("control_quote" in p for p in bad.problems)


def test_unknown_codes_are_reported() -> None:
    check = check_judgement(
        _judgement(
            obligation_code="OB-404", control_code="CTRL-404", coverage="none", control_quote=""
        ),
        obligation_codes=frozenset({"OB-001"}),
        control_texts={"CTRL-05": "text"},
    )
    assert any("unknown obligation_code" in p for p in check.problems)
    assert any("unknown control_code" in p for p in check.problems)


def test_verdict_flags_anything_with_problems() -> None:
    assert verdict_for(()) is Verdict.ACCEPTED
    assert verdict_for(("bad quote",)) is Verdict.NEEDS_REVIEW
