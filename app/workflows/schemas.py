"""Output schemas for model calls. The model fills these; the critic then checks them in code.

Fields the source does not state must be set to NOT_SPECIFIED, never guessed.
"""

from typing import Literal

from pydantic import BaseModel, Field

NOT_SPECIFIED = "Not specified"


class ObligationDraft(BaseModel):
    clause_ref: str = Field(
        description="The clause number exactly as it appears, e.g. '38' or '5A.1'."
    )
    source_quote: str = Field(
        description=(
            "The sentence(s) that create the obligation, "
            "copied character for character from the clause."
        )
    )
    topic: str = Field(description="Short topic label, e.g. 'periodic KYC updation'.")
    action: str = Field(description="What must be done, in plain English.")
    actor: str = Field(default=NOT_SPECIFIED, description="Who must act, if stated.")
    condition: str = Field(
        default=NOT_SPECIFIED, description="Condition that triggers the duty, if stated."
    )
    frequency: str = Field(default=NOT_SPECIFIED, description="How often, if stated.")
    deadline: str = Field(default=NOT_SPECIFIED, description="Deadline, if stated.")
    threshold: str = Field(default=NOT_SPECIFIED, description="Numeric threshold, if stated.")
    applicability: Literal["applicable", "not_applicable", "unknown"] = Field(
        default="applicable",
        description="Whether the clause applies to a scheduled commercial bank in India.",
    )
    applicability_reason: str = Field(
        default=NOT_SPECIFIED,
        description=(
            "Why it is not applicable, quoting the bank facts used. Required when not applicable."
        ),
    )


class ObligationBatch(BaseModel):
    obligations: list[ObligationDraft]


class ControlJudgement(BaseModel):
    obligation_code: str = Field(
        description="Code of the obligation being judged, exactly as given."
    )
    control_code: str = Field(description="Code of the control being judged, exactly as given.")
    coverage: Literal["covered", "partial", "none", "insufficient_info"]
    design: Literal["adequate", "inadequate", "unknown"]
    rationale: str = Field(description="One or two sentences explaining the judgement.")
    control_quote: str = Field(
        default="",
        description="Sentence from the control text that supports the judgement. Empty if none.",
    )


class MappingBatch(BaseModel):
    judgements: list[ControlJudgement]


class RemediationDraft(BaseModel):
    gap_code: str = Field(description="Code of the gap, exactly as given.")
    action: str = Field(description="Concrete corrective action.")
    owner_team: str = Field(description="Team that should own the action.")
    target_days: int = Field(description="Suggested days to complete, between 1 and 365.")
    closure_evidence: str = Field(description="Evidence that would prove the action is done.")


class RemediationBatch(BaseModel):
    drafts: list[RemediationDraft]
