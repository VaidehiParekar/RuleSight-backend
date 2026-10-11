"""Unit tests for deterministic gap rules and risk scoring (app.core.rules)."""

from app.core.rules import calculate_risk, evaluate_gap_type


def test_evaluate_gap_not_applicable() -> None:
    res = evaluate_gap_type(
        applicability="not_applicable",
        mappings_coverage=[],
    )
    assert res is None


def test_evaluate_gap_missing_control() -> None:
    # No mappings
    assert evaluate_gap_type("applicable", []) == "missing"
    # All none
    assert evaluate_gap_type("applicable", ["none", "none"]) == "missing"


def test_evaluate_gap_insufficient_info() -> None:
    assert evaluate_gap_type("applicable", ["covered", "insufficient_info"]) == "insufficient_info"


def test_evaluate_gap_compound_design_and_operating() -> None:
    # Partial coverage (treated as design inadequate) + ineffective operating
    assert (
        evaluate_gap_type(
            "applicable",
            ["partial"],
            design="inadequate",
            operating="ineffective",
        )
        == "design_operating"
    )


def test_evaluate_gap_design_alone() -> None:
    assert (
        evaluate_gap_type(
            "applicable",
            ["covered"],
            design="inadequate",
            operating="effective",
        )
        == "design"
    )


def test_evaluate_gap_operating_alone() -> None:
    assert (
        evaluate_gap_type(
            "applicable",
            ["covered"],
            design="adequate",
            operating="ineffective",
        )
        == "operating"
    )


def test_evaluate_gap_clean_no_gap() -> None:
    assert (
        evaluate_gap_type(
            "applicable",
            ["covered"],
            design="adequate",
            operating="effective",
        )
        is None
    )


def test_calculate_risk_p1_high_severity_high_criticality() -> None:
    # Topic financial_crime has criticality 3, missing has severity 3.0 -> 9.0 -> P1
    score, priority, factors = calculate_risk(
        topic="financial_crime",
        gap_type="missing",
        origin="initial",
    )
    assert score == 9.0
    assert priority == "P1"
    assert factors.criticality == 3
    assert factors.severity == 3.0
    assert factors.urgency == 1.0


def test_calculate_risk_with_change_urgency_boost() -> None:
    # Topic cdd has criticality 2, design has severity 2.0
    # initial score: 2 * 2.0 * 1.0 = 4.0 (P2)
    # change score: 2 * 2.0 * 1.5 = 6.0 (P1)
    score_init, p_init, _ = calculate_risk("cdd", "design", origin="initial")
    assert score_init == 4.0
    assert p_init == "P2"

    score_chg, p_chg, factors_chg = calculate_risk("cdd", "design", origin="change")
    assert score_chg == 6.0
    assert p_chg == "P1"
    assert factors_chg.urgency == 1.5
