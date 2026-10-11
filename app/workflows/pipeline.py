"""The AI pipeline as a LangGraph state graph.

    extract_obligations ──(no clauses)──► END
            │
            ▼
       map_controls ──(no gaps)──► END
            │
            ▼
     draft_remediation ──► END

Every node records an agent run (timing, model calls, error). A failing node is recorded and the
graph continues with empty results, so one bad call never takes the whole pipeline down.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from app.integrations.llm.base import LLMProviderError, StructuredLLMProvider, Usage, usage_of
from app.workflows.critic import Verdict
from app.workflows.schemas import ObligationDraft, RemediationDraft
from app.workflows.steps import (
    CandidateLink,
    ClauseInput,
    ControlInput,
    ExtractionResult,
    GapInput,
    MappingResult,
    MappingStepResult,
    ObligationInput,
    RemediationStepResult,
    Settled,
    draft_remediation,
    extract_obligations,
    keyword_candidates,
    map_controls,
)

NO_USAGE = Usage()

CandidateFinder = Callable[[Sequence[ObligationInput], Sequence[ControlInput]], list[CandidateLink]]
# Turns the mapping judgements into gaps with deterministic rules (no model call).
GapBuilder = Callable[[Sequence[ObligationInput], Sequence[MappingResult]], list[GapInput]]


@dataclass(frozen=True)
class AgentRun:
    node: str
    status: Literal["ok", "failed"]
    started_at: datetime
    ended_at: datetime
    llm_calls: int
    error: str | None = None
    usage: Usage = Usage()


@dataclass
class PipelineResult:
    obligations: list[Settled[str, ObligationDraft]] = field(default_factory=list)
    obligation_inputs: list[ObligationInput] = field(default_factory=list)
    mappings: list[MappingResult] = field(default_factory=list)
    gaps: list[GapInput] = field(default_factory=list)
    remediations: list[Settled[str, RemediationDraft]] = field(default_factory=list)
    runs: list[AgentRun] = field(default_factory=list)


class PipelineState(TypedDict, total=False):
    clauses: list[ClauseInput]
    controls: list[ControlInput]
    gaps: list[GapInput]
    obligations: list[Settled[str, ObligationDraft]]
    obligation_inputs: list[ObligationInput]
    mappings: list[MappingResult]
    remediations: list[Settled[str, RemediationDraft]]
    runs: list[AgentRun]


def _record(
    state: PipelineState,
    node: str,
    started: datetime,
    calls: int,
    error: str | None,
    usage: Usage = NO_USAGE,
) -> list[AgentRun]:
    run = AgentRun(
        node=node,
        status="failed" if error else "ok",
        started_at=started,
        ended_at=datetime.now(UTC),
        llm_calls=calls,
        error=error,
        usage=usage,
    )
    return [*state.get("runs", []), run]


def _obligation_inputs(settled: Sequence[Settled[str, ObligationDraft]]) -> list[ObligationInput]:
    inputs: list[ObligationInput] = []
    for index, item in enumerate(settled, start=1):
        if item.draft is None or item.verdict != Verdict.ACCEPTED:
            continue
        draft = item.draft
        inputs.append(
            ObligationInput(
                code=f"OB-{index:03d}",
                clause_ref=draft.clause_ref,
                topic=draft.topic,
                text=f"{draft.action} Source: {draft.source_quote}",
                applicability=draft.applicability,
            )
        )
    return inputs


def build_pipeline(
    provider: StructuredLLMProvider,
    *,
    candidate_finder: CandidateFinder = keyword_candidates,
    gap_builder: GapBuilder | None = None,
) -> Callable[[PipelineState], PipelineState]:
    """Compiles the graph. The provider and candidate finder are injected, so tests can use fakes
    and the knowledge-graph finder can replace the keyword finder without changing the graph.

    With a ``gap_builder``, gaps are derived from this run's mappings; without one, the gaps passed
    in the initial state are used."""

    def extract_node(state: PipelineState) -> PipelineState:
        started = datetime.now(UTC)
        metered = usage_of(provider)
        clauses = state.get("clauses", [])
        try:
            outcome: ExtractionResult = extract_obligations(provider, clauses)
        except LLMProviderError as exc:
            return {
                "obligations": [],
                "obligation_inputs": [],
                "runs": _record(
                    state, "extract_obligations", started, 1, str(exc), usage_of(provider) - metered
                ),
            }
        settled = outcome.obligations
        return {
            "obligations": settled,
            "obligation_inputs": _obligation_inputs(settled),
            "runs": _record(
                state,
                "extract_obligations",
                started,
                outcome.llm_calls,
                None,
                usage_of(provider) - metered,
            ),
        }

    def map_node(state: PipelineState) -> PipelineState:
        started = datetime.now(UTC)
        metered = usage_of(provider)
        obligations = state.get("obligation_inputs", [])
        controls = state.get("controls", [])
        candidates = candidate_finder(obligations, controls)
        try:
            outcome: MappingStepResult = map_controls(provider, obligations, controls, candidates)
        except LLMProviderError as exc:
            return {
                "mappings": [],
                "runs": _record(
                    state, "map_controls", started, 1, str(exc), usage_of(provider) - metered
                ),
            }
        update: PipelineState = {
            "mappings": outcome.mappings,
            "runs": _record(
                state,
                "map_controls",
                started,
                outcome.llm_calls,
                None,
                usage_of(provider) - metered,
            ),
        }
        if gap_builder is not None:
            update["gaps"] = gap_builder(obligations, outcome.mappings)
        return update

    def remediation_node(state: PipelineState) -> PipelineState:
        started = datetime.now(UTC)
        metered = usage_of(provider)
        gaps = state.get("gaps", [])
        try:
            outcome: RemediationStepResult = draft_remediation(provider, gaps)
        except LLMProviderError as exc:
            return {
                "remediations": [],
                "runs": _record(
                    state, "draft_remediation", started, 1, str(exc), usage_of(provider) - metered
                ),
            }
        return {
            "remediations": outcome.drafts,
            "runs": _record(
                state,
                "draft_remediation",
                started,
                outcome.llm_calls,
                None,
                usage_of(provider) - metered,
            ),
        }

    def after_extract(state: PipelineState) -> str:
        return "map_controls" if state.get("obligation_inputs") else END

    def after_map(state: PipelineState) -> str:
        return "draft_remediation" if state.get("gaps") else END

    graph: StateGraph[PipelineState] = StateGraph(PipelineState)
    graph.add_node("extract_obligations", extract_node)
    graph.add_node("map_controls", map_node)
    graph.add_node("draft_remediation", remediation_node)
    graph.add_edge(START, "extract_obligations")
    graph.add_conditional_edges("extract_obligations", after_extract)
    graph.add_conditional_edges("map_controls", after_map)
    graph.add_edge("draft_remediation", END)
    compiled = graph.compile()

    def run(state: PipelineState) -> PipelineState:
        return cast("PipelineState", compiled.invoke(state))

    return run


def run_pipeline(
    provider: StructuredLLMProvider,
    *,
    clauses: Sequence[ClauseInput],
    controls: Sequence[ControlInput],
    gaps: Sequence[GapInput] = (),
    candidate_finder: CandidateFinder = keyword_candidates,
    gap_builder: GapBuilder | None = None,
) -> PipelineResult:
    """Runs the pipeline end to end and returns plain results for the API layer to persist."""
    graph = build_pipeline(provider, candidate_finder=candidate_finder, gap_builder=gap_builder)
    final = graph(
        PipelineState(
            clauses=list(clauses),
            controls=list(controls),
            gaps=list(gaps),
        )
    )
    return PipelineResult(
        obligations=final.get("obligations", []),
        obligation_inputs=final.get("obligation_inputs", []),
        mappings=final.get("mappings", []),
        gaps=final.get("gaps", []),
        remediations=final.get("remediations", []),
        runs=final.get("runs", []),
    )
