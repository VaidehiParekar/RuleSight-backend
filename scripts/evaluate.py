"""Scores the stored pipeline results against the answer key and saves the report.

Usage:  uv run python -m scripts.evaluate

Reads ANSWER_KEY_PATH and writes EVAL_REPORT_PATH (see .env); GET /api/v1/eval/latest serves it.
The pipeline also runs this automatically at the end of every run.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.services.evaluation import run_evaluation


def main() -> None:
    result = run_evaluation(get_settings())
    if result is None:
        raise SystemExit("Set ANSWER_KEY_PATH and EVAL_REPORT_PATH in .env.")
    for metric in result.metrics:
        print(f"  {metric.label:24} {metric.value:.0%}")
    print(result.method)


if __name__ == "__main__":
    main()
