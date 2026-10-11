from pathlib import Path

from app.services.evaluation import (
    Expected,
    Found,
    document_sources,
    load_expected,
    paragraph_numbers,
    score,
    words,
)

KYC = "RBI KYC MD 2016"
ANSWER_KEY = Path("demo_data/3_answer_key/expected_mappings_RBI.csv")


def expected(key: str, para: int, summary: str, control: str | None, gap: str | None) -> Expected:
    return Expected(
        key=key,
        source=KYC,
        paragraphs=frozenset({para}),
        summary=summary,
        applicable=True,
        control=control,
        gap_type=gap,
    )


def found(
    id_: str, para: int, text: str, controls: set[str], gap: str | None, quote: str = ""
) -> Found:
    return Found(
        id=id_,
        document_text="Periodic updation shall be carried out once in every two years.",
        paragraph=para,
        words=words(text),
        source_quote=quote,
        applicable=True,
        controls=frozenset(controls),
        gap_type=gap,
        sources=frozenset({KYC}),
    )


def metric(result, key: str) -> float:  # type: ignore[no-untyped-def]
    return next(m.value for m in result.metrics if m.key == key)


def test_paragraph_labels_become_top_level_numbers() -> None:
    assert paragraph_numbers("18(a)(iv)") == {18}
    assert paragraph_numbers("2.2 / 4") == {2, 4}
    assert paragraph_numbers("5 (Tables 1-3)") == {5}
    assert paragraph_numbers("Testing Procedure") == set()


def test_documents_map_to_answer_key_sources() -> None:
    assert document_sources("RBI KYC Master Direction 2016 KYC.txt") == {KYC}
    assert document_sources("Master Direction on Note Sorting Machines 2 Oct 2026") == {
        "RBI NSM v2 (2026)"
    }
    assert document_sources("Note Sorting Machines circular 2024") == set()


def test_scores_recall_mapping_gaps_and_citations() -> None:
    key = [
        expected("OB-07", 38, "Periodic updation every 2 years for High risk", "CTL-05", "design"),
        expected("OB-10", 70, "On-going employee KYC/AML training programme", None, "missing"),
    ]
    results = [
        found(
            "a",
            38,
            "periodic updation high risk customers",
            {"CTL-05"},
            "design",
            quote="once in every two years",
        ),
        found("b", 12, "unrelated paragraph", set(), None),
    ]

    result = score(key, results)

    assert result.matched == {"OB-07": "a"}
    assert metric(result, "obligation_recall") == 0.5
    assert metric(result, "obligation_precision") == 1.0
    assert metric(result, "mapping_accuracy") == 1.0
    assert metric(result, "gap_recall") == 0.5
    assert metric(result, "gap_type_accuracy") == 1.0
    assert metric(result, "citation_validity") == 1.0


def test_nothing_to_score_reports_no_metrics() -> None:
    result = score([expected("OB-07", 38, "x", None, None)], [])

    assert result.metrics == []
    assert "No uploaded document" in result.notes[0]


def test_answer_key_file_loads() -> None:
    rows = load_expected(ANSWER_KEY)

    assert len(rows) == 20
    assert sum(1 for r in rows if r.gap_type) == 12
    assert next(r for r in rows if r.key == "OB-11").applicable is False
