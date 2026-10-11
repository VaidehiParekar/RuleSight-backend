"""Deterministic gap classification and risk calculation rules.

Pure functions without database or external dependencies, matching TEAM_PLAN_ONE_NIGHT.md §6 and §7.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas.domain import (
    Applicability,
    Coverage,
    DesignAssessment,
    GapType,
    OperatingAssessment,
    Priority,
    RiskFactors,
)


class RiskRules(BaseModel):
    """The risk formula's weights, loaded from the JSON file at RISK_RULES_PATH."""

    version: str
    criticality_default: int = Field(ge=1, le=3)
    criticality_by_topic_keyword: dict[str, int]
    severity_by_gap_type: dict[str, float]
    urgency_by_origin: dict[str, float]
    p1_threshold: float
    p2_threshold: float


@lru_cache(maxsize=4)
def load_risk_rules(path: Path) -> RiskRules:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RiskRules(
        version=data["version"],
        criticality_default=data["criticality"]["default"],
        criticality_by_topic_keyword=data["criticality"]["by_topic_keyword"],
        severity_by_gap_type=data["severity_by_gap_type"],
        urgency_by_origin=data["urgency_by_origin"],
        p1_threshold=data["priority_thresholds"]["P1"],
        p2_threshold=data["priority_thresholds"]["P2"],
    )


def risk_rules() -> RiskRules:
    return load_risk_rules(get_settings().risk_rules_path)


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
    rules = risk_rules()
    if custom_criticality is not None:
        criticality = custom_criticality
    else:
        topic_lower = topic.lower().replace(" ", "_").replace("-", "_")
        matches = [
            weight
            for keyword, weight in rules.criticality_by_topic_keyword.items()
            if keyword in topic_lower
        ]
        criticality = max(matches, default=rules.criticality_default)

    severity = rules.severity_by_gap_type.get(gap_type, 1.0)
    urgency = rules.urgency_by_origin.get(origin, 1.0)

    score = round(float(criticality) * severity * urgency, 2)

    if score >= rules.p1_threshold:
        priority: Priority = "P1"
    elif score >= rules.p2_threshold:
        priority = "P2"
    else:
        priority = "P3"

    factors = RiskFactors(
        criticality=criticality,
        severity=severity,
        urgency=urgency,
        rule_version=rules.version,
    )

    return score, priority, factors
