from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["P1", "P2", "P3"]
GapType = Literal["missing", "design", "operating", "design_operating", "insufficient_info"]
GapStatus = Literal["potential", "confirmed", "dismissed", "needs_info"]
GapOrigin = Literal["initial", "change"]
Coverage = Literal["covered", "partial", "none", "insufficient_info", "not_applicable"]
Applicability = Literal["applicable", "not_applicable", "unknown"]
ReviewStatus = Literal["suggested", "accepted", "rejected", "edited"]
MappingStatus = Literal["suggested", "accepted", "rejected", "needs_review"]
CriticResult = Literal["passed", "retried", "failed"]
DesignAssessment = Literal["adequate", "inadequate", "unknown"]
OperatingAssessment = Literal[
    "effective", "partially_effective", "ineffective", "insufficient_evidence", "not_applicable"
]
RemediationStatus = Literal[
    "draft", "approved", "in_progress", "completed", "verified", "rejected"
]
DocType = Literal["regulation", "policy", "rcm", "evidence"]
DocStatus = Literal["uploaded", "processing", "ready", "failed", "superseded"]
ChangeType = Literal["modified", "withdrawn", "corpus_gap", "consolidated"]
Significance = Literal["high", "medium", "low", "administrative"]
NodeStatus = Literal["queued", "running", "done", "retried", "failed"]


class SourceDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doc_type: DocType
    title: str
    reference: str = ""
    regulator: str | None = None
    version_label: str = ""
    supersedes_id: str | None = None
    is_synthetic: bool = False
    status: DocStatus = "ready"
    withdrawn_note: str | None = None
    created_at: str
    sha256: str = ""
    chunk_count: int = 0
    obligation_count: int = 0


class Obligation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    document_id: str
    source_label: str
    clause_ref: str
    page: int | None = None
    source_quote: str
    key_phrase: str | None = None
    quote_verified: bool = False
    summary: str
    actor: str
    action: str
    condition: str | None = None
    frequency: str | None = None
    deadline: str | None = None
    threshold: str | None = None
    topic: str
    criticality: int
    applicability: Applicability
    applicability_reason: str | None = None
    coverage: Coverage = "none"
    review_status: ReviewStatus = "suggested"


class Control(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str
    owner: str
    frequency: str
    control_type: str = "Detective"
    automation: str = "Manual"
    source_document: str = ""
    source_section: str = ""
    source_quote: str | None = None
    evidence_expected: str = ""
    rbi_reference: str = ""
    topic: str


class Evidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    title: str
    file_name: str
    control_codes: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    flagged_cells: list[list[int]] = Field(default_factory=list)
    summary: str


class Mapping(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    obligation_id: str
    control_id: str
    coverage: Coverage
    rationale: str
    graph_path: list[str] = Field(default_factory=list)
    critic: CriticResult = "passed"
    status: MappingStatus = "suggested"


class Assessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    obligation_id: str
    design: DesignAssessment
    design_note: str
    operating: OperatingAssessment
    operating_note: str
    evidence_ids: list[str] = Field(default_factory=list)


class RiskFactors(BaseModel):
    criticality: float | int
    severity: float | int
    urgency: float | int
    rule_version: str = "v1"


class Gap(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    obligation_id: str
    gap_type: GapType
    title: str
    description: str
    control_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    origin: GapOrigin = "initial"
    change_id: str | None = None
    risk_factors: RiskFactors
    risk_score: float
    priority: Priority
    status: GapStatus = "potential"
    dismissed_reason: str | None = None


class Remediation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gap_id: str
    action: str
    owner_team: str
    target_days: int
    closure_evidence: str
    status: RemediationStatus = "draft"


class RegulatoryChange(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    old_document_id: str
    new_document_id: str
    clause_ref: str
    change_type: ChangeType
    title: str
    old_text: str | None = None
    new_text: str | None = None
    summary: str
    significance: Significance
    carried_over: list[str] = Field(default_factory=list)
    impact: dict[str, Any] = Field(default_factory=dict)


class MissingCircular(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row: int
    reference: str
    date: str
    subject: str


class ChangeComparisonResponse(BaseModel):
    old_document: SourceDocument
    new_document: SourceDocument
    changes: list[RegulatoryChange]
    missing_circulars: list[MissingCircular]


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    at: str
    actor: str
    actor_role: str
    action: str
    entity_type: str
    entity_code: str
    reason: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class RunNode(BaseModel):
    node: str
    status: NodeStatus
    offset_ms: int
    duration_ms: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    note: str | None = None
    conditional: bool = False


class AgentRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    started_at: str
    trigger: str
    cache_hits: int
    status: str
    nodes: list[RunNode] = Field(default_factory=list)


class GapTrace(BaseModel):
    gap: Gap
    obligation: Obligation
    document: SourceDocument
    controls: list[Control]
    mappings: list[Mapping]
    assessment: Assessment | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    remediations: list[Remediation] = Field(default_factory=list)
    change: RegulatoryChange | None = None
    audit: list[AuditEntry] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    obligations_total: int
    obligations_applicable: int
    obligations_not_applicable: int
    coverage: dict[str, int]
    open_gaps: int
    gaps_by_priority: dict[str, int]
    gaps_by_type: list[dict[str, Any]]
    risk_exposure: float
    remediation_approved: int
    remediation_total: int
    next_deadline: dict[str, Any]
    review: dict[str, Any]
    critic_retries: int
    llm_calls: int
    last_run_at: str


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    detail: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class EvalMetric(BaseModel):
    key: str
    label: str
    value: float


class EvalReport(BaseModel):
    is_mock: bool = False
    scored_at: str | None = None
    method: str = ""
    metrics: list[EvalMetric]


RoleType = Literal["admin", "compliance_officer", "compliance_analyst", "auditor"]


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    initials: str
    is_active: bool = True
    created_at: str | None = None
    last_login_at: str | None = None
    permissions: list[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


