"""The three model-backed steps: obligation extraction, control mapping, remediation drafting.

Each step follows the same loop:
1. Ask the model once for every item in the batch.
2. Check every answer with the deterministic critic (app.workflows.critic).
3. Send only the failing items back once, with the exact problems listed.
4. Anything still failing is kept and marked NEEDS_REVIEW. Nothing is silently dropped.
"""

from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from app.integrations.llm.base import StructuredLLMProvider
from app.workflows import prompts
from app.workflows.critic import (
    Verdict,
    check_judgement,
    check_obligation,
    verdict_for,
)
from app.workflows.schemas import (
    ControlJudgement,
    MappingBatch,
    ObligationBatch,
    ObligationDraft,
    RemediationBatch,
    RemediationDraft,
)

STEP_TIMEOUT_SECONDS = 60.0


# ---------------------------------------------------------------- inputs


@dataclass(frozen=True)
class ClauseInput:
    clause_ref: str
    text: str


@dataclass(frozen=True)
class ControlInput:
    code: str
    name: str
    text: str


@dataclass(frozen=True)
class ObligationInput:
    code: str
    clause_ref: str
    topic: str
    text: str


@dataclass(frozen=True)
class CandidateLink:
    obligation_code: str
    control_code: str
    path: str


@dataclass(frozen=True)
class GapInput:
    code: str
    obligation_code: str
    gap_type: str
    description: str
    control_names: tuple[str, ...]


# ---------------------------------------------------------------- results


@dataclass(frozen=True)
class Settled[K: Hashable, D: BaseModel]:
    """One accepted or flagged answer for a key (a clause, a mapping pair, or a gap)."""

    key: K
    draft: D | None
    problems: tuple[str, ...]

    @property
    def verdict(self) -> Verdict:
        return verdict_for(self.problems)


# ---------------------------------------------------------------- generic loop


def _ask[D: BaseModel](
    provider: StructuredLLMProvider,
    prompt: str,
    schema: type[D],
) -> D:
    return provider.generate_structured(
        prompt=prompt,
        schema=schema,
        timeout_seconds=STEP_TIMEOUT_SECONDS,
    )


def solve[K: Hashable, D: BaseModel](
    keys: Sequence[K],
    *,
    call: Callable[[list[K], Mapping[K, tuple[str, ...]]], Iterable[tuple[K, D]]],
    check: Callable[[K, D], tuple[str, ...]],
) -> tuple[list[Settled[K, D]], int]:
    """Runs the generate, check, retry-once, flag loop.
    Returns settled answers and the call count.
    """

    requested = list(keys)
    wanted = set(requested)

    def group(answers: Iterable[tuple[K, D]]) -> dict[K, list[D]]:
        grouped: dict[K, list[D]] = {}
        for key, draft in answers:
            if key in wanted:
                grouped.setdefault(key, []).append(draft)
        return grouped

    def problems_for(key: K, drafts: list[D]) -> tuple[str, ...]:
        if not drafts:
            return ("no answer was returned for this item",)
        collected: list[str] = []
        for draft in drafts:
            collected.extend(check(key, draft))
        return tuple(collected)

    answers = group(call(requested, {}))
    calls = 1

    failing = [k for k in requested if problems_for(k, answers.get(k, []))]
    if failing:
        notes = {k: problems_for(k, answers.get(k, [])) for k in failing}
        retry = group(call(failing, notes))
        calls += 1
        for key in failing:
            if retry.get(key):
                answers[key] = retry[key]

    settled: list[Settled[K, D]] = []
    for key in requested:
        drafts = answers.get(key, [])
        if not drafts:
            settled.append(Settled(key, None, problems_for(key, [])))
            continue
        for draft in drafts:
            settled.append(Settled(key, draft, check(key, draft)))
    return settled, calls


# ---------------------------------------------------------------- step 1: obligations


@dataclass(frozen=True)
class ExtractionResult:
    obligations: list[Settled[str, ObligationDraft]]
    llm_calls: int


def extract_obligations(
    provider: StructuredLLMProvider,
    clauses: Sequence[ClauseInput],
) -> ExtractionResult:
    clause_texts = {c.clause_ref: c.text for c in clauses}
    by_ref = {c.clause_ref: c for c in clauses}

    def call(
        keys: list[str],
        notes: Mapping[str, tuple[str, ...]],
    ) -> Iterable[tuple[str, ObligationDraft]]:
        batch_clauses = [by_ref[k] for k in keys]
        prompt = prompts.obligations_prompt(batch_clauses, notes)
        response = _ask(provider, prompt, ObligationBatch)
        return [(d.clause_ref, d) for d in response.obligations]

    def check(key: str, draft: ObligationDraft) -> tuple[str, ...]:
        return check_obligation(draft, clause_texts).problems

    settled, calls = solve([c.clause_ref for c in clauses], call=call, check=check)
    return ExtractionResult(obligations=settled, llm_calls=calls)


# ---------------------------------------------------------------- step 2: mapping


@dataclass(frozen=True)
class MappingResult:
    obligation_code: str
    control_code: str
    judgement: ControlJudgement | None
    problems: tuple[str, ...]

    @property
    def verdict(self) -> Verdict:
        return verdict_for(self.problems)


@dataclass(frozen=True)
class MappingStepResult:
    mappings: list[MappingResult]
    llm_calls: int


def map_controls(
    provider: StructuredLLMProvider,
    obligations: Sequence[ObligationInput],
    controls: Sequence[ControlInput],
    candidates: Sequence[CandidateLink],
) -> MappingStepResult:
    if not candidates:
        return MappingStepResult(mappings=[], llm_calls=0)

    control_texts = {c.code: c.text for c in controls}
    obligation_codes = frozenset(o.code for o in obligations)
    pairs: list[tuple[str, str]] = [(c.obligation_code, c.control_code) for c in candidates]
    by_pair = {(c.obligation_code, c.control_code): c for c in candidates}
    obligations_by_code = {o.code: o for o in obligations}
    controls_by_code = {c.code: c for c in controls}

    def call(
        keys: list[tuple[str, str]],
        notes: Mapping[tuple[str, str], tuple[str, ...]],
    ) -> Iterable[tuple[tuple[str, str], ControlJudgement]]:
        batch = [by_pair[k] for k in keys]
        prompt = prompts.mapping_prompt(
            obligations=[obligations_by_code[c.obligation_code] for c in batch],
            controls=[controls_by_code[c.control_code] for c in batch],
            candidates=batch,
            notes=notes,
        )
        response = _ask(provider, prompt, MappingBatch)
        return [((j.obligation_code, j.control_code), j) for j in response.judgements]

    def check(key: tuple[str, str], judgement: ControlJudgement) -> tuple[str, ...]:
        return check_judgement(
            judgement,
            obligation_codes=obligation_codes,
            control_texts=control_texts,
        ).problems

    settled, calls = solve(pairs, call=call, check=check)
    mappings = [
        MappingResult(
            obligation_code=s.key[0],
            control_code=s.key[1],
            judgement=s.draft,
            problems=s.problems,
        )
        for s in settled
    ]
    return MappingStepResult(mappings=mappings, llm_calls=calls)


# ---------------------------------------------------------------- step 3: remediation


def _check_remediation(draft: RemediationDraft) -> tuple[str, ...]:
    problems: list[str] = []
    if not draft.action.strip():
        problems.append("action is empty")
    if not draft.owner_team.strip():
        problems.append("owner_team is empty")
    if not 1 <= draft.target_days <= 365:
        problems.append("target_days must be between 1 and 365")
    if not draft.closure_evidence.strip():
        problems.append("closure_evidence is empty")
    return tuple(problems)


@dataclass(frozen=True)
class RemediationStepResult:
    drafts: list[Settled[str, RemediationDraft]]
    llm_calls: int


def draft_remediation(
    provider: StructuredLLMProvider,
    gaps: Sequence[GapInput],
) -> RemediationStepResult:
    if not gaps:
        return RemediationStepResult(drafts=[], llm_calls=0)
    by_code = {g.code: g for g in gaps}

    def call(
        keys: list[str],
        notes: Mapping[str, tuple[str, ...]],
    ) -> Iterable[tuple[str, RemediationDraft]]:
        prompt = prompts.remediation_prompt([by_code[k] for k in keys], notes)
        response = _ask(provider, prompt, RemediationBatch)
        return [(d.gap_code, d) for d in response.drafts]

    def check(key: str, draft: RemediationDraft) -> tuple[str, ...]:
        return _check_remediation(draft)

    settled, calls = solve([g.code for g in gaps], call=call, check=check)
    return RemediationStepResult(drafts=settled, llm_calls=calls)


# ---------------------------------------------------------------- candidates


def keyword_candidates(
    obligations: Iterable[ObligationInput],
    controls: Iterable[ControlInput],
) -> list[CandidateLink]:
    """Fallback candidate finder: an obligation and a control are candidates when they share a
    meaningful word in their topic and text. The knowledge-graph finder replaces this when built."""
    stop = {"the", "and", "for", "of", "to", "a", "an", "in", "on", "by", "with", "at", "is"}

    def words(text: str) -> set[str]:
        return {w.lower().strip(".,;:()'\"") for w in text.split()} - stop - {""}

    links: list[CandidateLink] = []
    control_list = list(controls)
    for obligation in obligations:
        topic_words = words(obligation.topic) | words(obligation.text)
        for control in control_list:
            shared = sorted(topic_words & (words(control.name) | words(control.text)))
            if len(shared) >= 2:
                links.append(
                    CandidateLink(
                        obligation_code=obligation.code,
                        control_code=control.code,
                        path=f"shared terms: {', '.join(shared[:6])}",
                    )
                )
    return links
