"""Re-export from app.core.rules for backward compatibility."""

from app.core.rules import (
    CRITICALITY_MAP,
    SEVERITY_MAP,
    calculate_risk,
    evaluate_gap_type,
)

__all__ = [
    "CRITICALITY_MAP",
    "SEVERITY_MAP",
    "calculate_risk",
    "evaluate_gap_type",
]
