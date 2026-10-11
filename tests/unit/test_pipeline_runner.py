from datetime import UTC, datetime, timedelta

from app.integrations.llm.base import Usage
from app.services.pipeline_runner import _Control, _node_rows, _Totals, make_gap_builder
from app.workflows.pipeline import AgentRun as NodeRecord
from app.workflows.schemas import ControlJudgement
from app.workflows.steps import MappingResult, ObligationInput

CONTROLS = {"CTL-05": _Control(id="ctl-05", code="CTL-05", name="Periodic KYC update")}


def obligation(code: str, applicability: str = "applicable") -> ObligationInput:
    return ObligationInput(
        code=code, clause_ref="38", topic="periodic updation", text="", applicability=applicability
    )


def judged(code: str, coverage: str, design: str = "adequate") -> MappingResult:
    return MappingResult(
        obligation_code=code,
        control_code="CTL-05",
        judgement=ControlJudgement(
            obligation_code=code,
            control_code="CTL-05",
            coverage=coverage,  # type: ignore[arg-type]
            design=design,  # type: ignore[arg-type]
            rationale=f"{code} is {coverage}.",
        ),
        problems=(),
    )


def test_gap_rules_follow_the_rule_tree() -> None:
    build = make_gap_builder(CONTROLS)
    obligations = [
        obligation("OB-001"),
        obligation("OB-002"),
        obligation("OB-003"),
        obligation("OB-004", "not_applicable"),
    ]
    mappings = [
        judged("OB-001", "covered"),
        judged("OB-002", "partial", "inadequate"),
    ]

    gaps = build(obligations, mappings)

    by_obligation = {g.obligation_code: g for g in gaps}
    assert set(by_obligation) == {"OB-002", "OB-003"}
    assert by_obligation["OB-002"].gap_type == "design"
    assert by_obligation["OB-002"].control_names == ("Periodic KYC update",)
    assert by_obligation["OB-003"].gap_type == "missing"
    assert by_obligation["OB-003"].description == "No existing control addresses this duty."
    assert len({g.code for g in gaps}) == len(gaps)


def test_node_rows_sum_records_and_mark_skipped_nodes() -> None:
    start = datetime(2026, 10, 11, tzinfo=UTC)
    totals = _Totals()
    totals.records["extract_obligations"] = [
        NodeRecord(
            node="extract_obligations",
            status="ok",
            started_at=start + timedelta(milliseconds=100),
            ended_at=start + timedelta(seconds=2),
            llm_calls=2,
            usage=Usage(cache_hits=0, input_tokens=900, output_tokens=120),
        )
    ]

    rows = _node_rows(totals, start, None)

    extract, mapping, _ = rows
    assert extract["status"] == "done"
    assert extract["offset_ms"] == 100
    assert extract["duration_ms"] == 1900
    assert (extract["llm_calls"], extract["input_tokens"], extract["output_tokens"]) == (
        2,
        900,
        120,
    )
    assert mapping["note"] == "Skipped: nothing to do at this step."


def test_failed_run_reports_reason_on_every_node() -> None:
    rows = _node_rows(_Totals(), datetime.now(UTC), "Set LLM_PROVIDER=gemini")

    assert {r["status"] for r in rows} == {"failed"}
    assert {r["note"] for r in rows} == {"Set LLM_PROVIDER=gemini"}
