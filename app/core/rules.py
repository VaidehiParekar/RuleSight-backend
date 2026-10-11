"""Deterministic gap classification and risk calculation rules.

Pure functions without database or external dependencies, matching TEAM_PLAN_ONE_NIGHT.md §6 and §7.
"""

from typing import Literal

from app.schemas.domain import (
    Applicability,
    Coverage,
    DesignAssessment,
    GapType,
    OperatingAssessment,
    Priority,
    RiskFactors,
)

CRITICALITY_MAP: dict[str, int] = {
    # Criticality 3: Regulatory reporting, financial crime, data security
    "financial_crime": 3,
    "reporting": 3,
    "security": 3,
    "data_protection": 3,
    "str_ctr": 3,
    "cdd": 2,
    "onboarding": 2,
    "v-cip": 2,
    "currency_handling": 2,
    "nsm": 2,
    "note_sorting": 2,
    "governance": 1,
    "training": 1,
    "documentation": 1,
}

SEVERITY_MAP: dict[GapType, float] = {
    "missing": 3.0,
    "design_operating": 3.0,
    "design": 2.0,
    "operating": 1.5,
    "insufficient_info": 1.0,
}


def evaluate_gap_type(
    applicability: Applicability,
    mappings_coverage: list[Coverage],
    design: DesignAssessment | None = None,
    operating: OperatingAssessment | None = None,
) -> GapType | None:
    """Determines the gap category for an obligation using the deterministic 5-rule tree.

    Returns None if there is no gap (e.g. fully covered and adequate, or not applicable).
    """
    if applicability != "applicable":
        return None

    # Rule 1: No mapping or all mappings are none -> Missing control
    valid_mappings = [c for c in mappings_coverage if c in ("covered", "partial")]
    if not valid_mappings:
        return "missing"

    # Rule 2: Any mapping with insufficient_info -> Insufficient info
    if any(c == "insufficient_info" for c in mappings_coverage):
        return "insufficient_info"

    has_partial = any(c == "partial" for c in mappings_coverage)
    is_design_inadequate = has_partial or (design == "inadequate")
    is_operating_ineffective = operating in ("partially_effective", "ineffective")

    # Rule 3: Compound failure
    if is_design_inadequate and is_operating_ineffective:
        return "design_operating"

    # Rule 4: Design deficiency alone
    if is_design_inadequate:
        return "design"

    # Rule 5: Operating deficiency alone
    if is_operating_ineffective:
        return "operating"

    # Operating insufficient_evidence alone is NOT a gap (system abstains)
    return None


def calculate_risk(
    topic: str,
    gap_type: GapType,
    origin: Literal["initial", "change"] = "initial",
    custom_criticality: int | None = None,
) -> tuple[float, Priority, RiskFactors]:
    """Calculates risk_score = criticality * severity * urgency and assigns P1/P2/P3 priority."""
    if custom_criticality is not None:
        criticality = custom_criticality
    else:
        topic_lower = topic.lower().replace(" ", "_").replace("-", "_")
        criticality = 1
        for key, val in CRITICALITY_MAP.items():
            if key in topic_lower:
                criticality = val
                break

    severity = SEVERITY_MAP.get(gap_type, 1.0)
    urgency = 1.5 if origin == "change" else 1.0

    score = round(float(criticality) * severity * urgency, 2)

    if score >= 6.0:
        priority: Priority = "P1"
    elif score >= 3.0:
        priority = "P2"
    else:
        priority = "P3"

    factors = RiskFactors(
        criticality=criticality,
        severity=severity,
        urgency=urgency,
        rule_version="v1",
    )

    return score, priority, factors
