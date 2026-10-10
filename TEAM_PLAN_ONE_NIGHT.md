# RuleSight: one-night build plan

**Team:** Akhi, Vedant, Vaidehi, Anand · **Goal:** a working demo and an architecture document for ET AI Hackathon Problem 1 · **Claim:** D2 × F3

Read this whole file before anyone writes code. Sections 4 and 5 are the **contract** between frontend, backend and agents. Do not change them without telling everyone.

---

## 0. Decisions already made (do not re-debate tonight)

| Topic | Decision | Why |
|---|---|---|
| Grid claim | **D2 × F3** | F3 means 8+ features, and we build 8 core + up to 4 stretch. D2 means we **measure** accuracy against `demo_data/3_answer_key/`. D3 (multimodal) only if image evidence works live; otherwise we lose points for overclaiming. |
| LLM | **`gemini-2.5-flash`** through the **`google-genai`** SDK | **Gemini 1.5 Flash is retired.** Google shut it down in 2025, and calls return "model not found". If AI Studio shows a newer free Flash model, use that. Put the name in `.env` (`LLM_MODEL`) so changing it is one line. |
| Retrieval (RAG) | **Optional.** The selected regulation paragraphs (about 30 KYC paragraphs and the NSM pages) are small enough to put straight into the prompt. No embeddings tonight. Candidate controls come from the knowledge graph. | Less infrastructure and fewer failure points. Add RAG only if time is left at H8. |
| SDK | `pip/uv add google-genai` → `from google import genai` | **Not** `google-generativeai`. That is the old SDK the antigravity docs use. |
| Database | The existing Postgres 17 scaffold. **Postgres is the source of truth.** | Do **not** add SQLite, ChromaDB, Neo4j, Redis or Celery. |
| Knowledge graph | **In-memory NetworkX `MultiDiGraph`**, built from Postgres at startup and after each pipeline run (see §4b) | Real graph traversal for mapping candidates, impact analysis and the trace. A restart loses nothing because the graph is rebuilt from Postgres. |
| Orchestration | **LangGraph**: one `StateGraph` with conditional edges | This gives the "agentic" story (routing, retries, self-correction) without building 10 separate agents. |
| Background jobs | FastAPI `BackgroundTasks` | No Celery. |
| Auth | **Skipped.** A frontend dropdown "Acting as: Priya (Compliance Officer) / Rahul (Analyst)" sends an `X-Actor` header | We still get human-in-the-loop and an audit trail with names. Say "auth is out of scope for the prototype" in the doc. |
| File storage | Local folder `backend/storage/` | |
| Demo data | `demo_data/`: **RBI-only corpus.** Real RBI KYC Master Direction (text) and Note Sorting Machine v1 (2024, withdrawn) and v2 (2026 Master Direction) PDFs. Nova Trust Bank (policies, RCM, evidence) is fictional but cites only real RBI paragraphs. No CBA, no synthetic regulator. | Real RBI text = credibility. Answer keys in `3_answer_key/` measure accuracy. |

### Free-tier survival rules (very important)
1. **Cache every LLM call.** Store results in table `llm_cache(prompt_hash, model, response_json)`. Reruns cost nothing, and the demo becomes **deterministic**.
2. **Batch calls.** Use one call per document for obligation extraction, not one per clause. A full pipeline run should need **about 80–100 calls**.
3. Each person uses **their own** AI Studio key during development. Check the current free-tier limits in AI Studio, because the per-day cap is the real limit.
4. Use `temperature=0` and **structured output** (`response_schema=` a Pydantic model) on every call.
5. Before the demo, **pre-run the full pipeline and `pg_dump` the database.** On stage, run one live step (the NSM v2 upload). If the API fails, restore the dump.

---

## 1. Verdict on the antigravity docs (`Downloads/docs (1)/docs`)

**Keep these ideas:**
- The risk-control-matrix (RCM) column model
- The three gap types (missing, design, operating)
- The critic checks: the citation exists, the quote is verbatim, and the modality is satisfied
- Pydantic validation with retry
- Clause-level chunking with citation coordinates
- The orphan-obligation query (`NOT EXISTS`)
- The approve button
- The demo script shape

**Throw away or fix:**

| Problem in the docs | Fix |
|---|---|
| Gemini 1.5 Flash/Pro, `google-generativeai`, `text-embedding-004`, "2M context / 15 RPM" | These are retired or stale. Use the choices in §0. |
| SQLite + ChromaDB + Neo4j + Celery/Redis + Streamlit + PyVis + `requirements.txt` + `start.py` | This doesn't match our scaffold (Postgres + pgvector, uv, Alembic, `app/api/v1`). Use the scaffold. |
| Invented grid rules ("F1 = 3–5 features", "D2 requires a knowledge graph", "judges reward…") | Not in the problem statement. The brief only says **at least 3 / 6 / 8**. |
| One doc claims D3, another says D2 while "presenting D3" | Claiming one cell and showing another gets penalised. We claim **D2 × F3** everywhere. |
| Features named "F1–F14" | These clash with grid levels F1–F3. Call features **#1–#14**. |
| "Zero Hallucination Guarantee", "100% deterministic", "42% SLA breach", "$120,000" | Unsupported claims that judges will probe. Replace them with **our measured numbers**. |
| Real-regulation "facts" (circular numbers, clause numbers, "DPDP vs PMLA contradiction", PCI-DSS 3.4, ISO A.10.1) | Partly wrong. Use the RBI-only corpus. Never quote a real clause you haven't checked in the PDF. |
| DocSync agent (git diffs → DECISION_LOG) | That's the AI tool's own workflow leaking in. Delete it. |
| 10 agents, BM25, SAT solver, Jira, Langfuse, crypto signatures, OCR deskew | Overscoped for one night. Cut. |
| Applicability and Testing stages missing | We add an applicability step and an evidence assessment step (§3). |

---

## 2. Feature scope

| # | Feature | Tier | How (in short) | Owner |
|---|---|---|---|---|
| 1 | Ingestion | **Core** | Upload PDF/MD/CSV → text → clause-level chunks (with clause_ref) | Vedant |
| 3 | Obligation extraction | **Core** | Gemini returns structured JSON + a **verbatim** `source_quote` | Akhi |
| 4 | Control framework | **Core** | Parse the RCM CSV directly; LLM-extract controls from policy MD/PDF | Akhi |
| 5 | Regulation→control mapping | **Core** | KG candidate controls (same topic or owner, found by graph traversal) → Gemini judge → critic | Akhi |
| 8 | Gap identification | **Core** | **Deterministic rules** on mappings and assessments | Vedant |
| 9 | Risk prioritisation | **Core** | Documented formula (§6) | Vedant |
| 10 | Remediation | **Core** | Gemini drafts → human approves | Akhi |
| 2 | Change intelligence | **Core** | Two modes: (a) same structure → `difflib` by clause number; (b) different structure (circular → Master Direction) → **obligation-level** match via topic keywords + Gemini. Also reads "withdrawn" annexes/watermarks | Anand |
| 11 | Impact analysis | Stretch 1 | Changed clauses → old obligations → mappings → re-run for affected items | Anand |
| 6+7 | Control effectiveness + evidence | Stretch 1 | Gemini reads the evidence CSV/MD per control → design/operating status | Akhi |
| 13 | Cross-regulation | **Dropped** | No real overlap or conflict in the RBI-only corpus. Do not claim it. | - |
| 14 | Contradiction detection | **Dropped** | No real conflict in the RBI-only corpus. Do not claim it. | - |
| 12 | What-if | **Skip** | Mention it as future work | — |

Core = 8 features, which is F3. With stretch 1 that's 11; with all stretch items it's 13. **Claim only what works in the demo.**

---

## 3. Architecture

```
React (Vaidehi)  ──HTTP──▶  FastAPI /api/v1  (Vedant)
                                │
               ┌────────────────┼──────────────────────────────┐
               ▼                ▼                              ▼
        Ingestion service   LangGraph pipeline (Akhi/Anand)   Read/Review APIs
        (parse, chunk,      ┌───────────────────────────────┐  (+ audit_log on
         index)             │ extract_obligations           │   every change)
                            │   → check_applicability        │
                            │ extract_controls (or RCM CSV)  │
                            │   → map (KG candidates + LLM) │
                            │   → critic ──fail──▶ retry once │
                            │        └─fail again▶needs_review│
                            │   → assess_evidence            │
                            │   → detect_gaps   (rules)      │
                            │   → score_risk    (formula)    │
                            │   → draft_remediation          │
                            │ if doc.supersedes_id:          │
                            │   → diff_versions → impact     │
                            │   → re-map affected → new gaps │
                            └───────────────────────────────┘
                                │                │
                         PostgreSQL (source of truth)   Gemini (google-genai)
                         (all records,  with llm_cache table
                          llm_cache, agent_runs)
```

**What makes it agentic (say this to the judges):**
- **Conditional routing.** The graph routes by document type. A new version automatically triggers the change → impact branch.
- **Tool use.** Nodes call `kg_candidates(obligation_id)`, `kg_impact(clause_ref)` and `read_evidence(id)`.
- **Self-correction.** The critic checks the quote with code: `source_quote in document_text`. It also checks that the cited control ID exists. On failure it retries with the error message; if it fails again, the item goes to `needs_review`.
- **Abstention.** If there's no evidence, the status is `insufficient_evidence`. The system never guesses "compliant".
- **Human-in-the-loop.** Nothing becomes "confirmed" without an approve action, and every action is written to `audit_log`.
- **Observability.** Every node writes a row in `agent_runs` (timings, LLM calls, tokens, errors). Show this in the UI.

**Confidence (follows the spec rule "no fake probabilities"):** show the **graph path** that justifies each candidate (for example Obligation → topic CDD ← Control) plus the **critic pass/fail**. Don't show "LLM confidence 92%".

---

## 4. Database (Vedant: one Alembic migration)

All IDs are UUIDs, and every table has `created_at`. Enums are text with CHECK constraints.

```
documents(id, doc_type[regulation|policy|rcm|evidence], title, regulator, version_label,
          supersedes_id→documents, is_synthetic bool, file_path, sha256 UNIQUE, status[uploaded|processing|ready|failed], error)
chunks(id, document_id, clause_ref, page, text)
obligations(id, document_id, code, clause_ref, source_quote, actor, action, condition, frequency,
            deadline, threshold, topic, criticality[1-3], applicability[applicable|not_applicable|unknown],
            applicability_reason, review_status[suggested|accepted|rejected|edited])
controls(id, code, name, description, owner, frequency, source_document_id, source_section,
         source_quote)
evidence(id, document_id, control_code, summary)
mappings(id, obligation_id, control_id, coverage[covered|partial|none|insufficient_info],
         rationale, similarity, critic_passed, status[suggested|accepted|rejected|needs_review])
assessments(id, mapping_id, design[adequate|inadequate|unknown],
            operating[effective|partially_effective|ineffective|insufficient_evidence],
            rationale, evidence_ids jsonb, cited_quotes jsonb, review_status)
gaps(id, obligation_id, gap_type[missing|design|operating|design_operating|insufficient_info],
     description, control_ids jsonb, origin[initial|change], change_id, risk_score, priority[P1|P2|P3],
     risk_factors jsonb, status[potential|confirmed|dismissed|needs_info])
remediations(id, gap_id, action, owner_team, target_days, closure_evidence,
             status[draft|approved|in_progress|completed|verified|rejected])
changes(id, old_document_id, new_document_id, clause_ref, change_type[added|deleted|modified],
        old_text, new_text, summary, significance[high|medium|low|administrative], review_status)
audit_log(id, actor, action, entity_type, entity_id, before jsonb, after jsonb, at)   -- insert only
agent_runs(id, run_id, node, status, started_at, ended_at, llm_calls, input_tokens, output_tokens, error)
llm_cache(prompt_hash PK, model, response jsonb)
```

---

## 4b. Knowledge graph (in memory, NetworkX)

The graph is an **in-memory `networkx.MultiDiGraph`** built by `app/kg.py`. Postgres stays the source of truth: `rebuild_kg(session)` loads the rows and rebuilds the graph at startup and after each pipeline run. The LLM never writes to the graph. It only writes to Postgres.

**Nodes:** `clause` (regulation paragraph), `obligation`, `control`, `evidence`, `topic` (for example CDD, V-CIP, NSM-testing), `gap`, `remediation`, `change`, `document`.

**Edges:**

| Edge | From → To | Meaning |
|---|---|---|
| `DERIVED_FROM` | obligation → clause | obligation was extracted from this paragraph |
| `ABOUT` | obligation → topic | the obligation's topic |
| `ABOUT` | control → topic | the control's topic (set when the control is extracted or entered) |
| `COVERED_BY` | obligation → control | mapping, with `coverage` and `status` as attributes |
| `SUPPORTED_BY` | control → evidence | evidence attached to the control |
| `ON` | gap → obligation | the gap is about this obligation |
| `INVOLVES` | gap → control | controls involved in the gap |
| `MODIFIES` | change → clause | the v1 to v2 change touched this clause |
| `AFFECTED` | change → obligation | the change affects this obligation |
| `SUPERSEDES` | document → document | version chain (NSM v2 supersedes v1) |

**Queries used in the pipeline and the demo:**

| Function | What it does | Used by |
|---|---|---|
| `kg_candidates(obligation_id)` | controls that share a topic with the obligation, or sit two hops away through a shared control owner. Returns the path for each candidate. | map node (feeds the LLM judge) |
| `kg_impact(clause_ref)` | clause → obligations (`DERIVED_FROM`) → controls (`COVERED_BY`) → gaps (`ON`). Traverses the graph and returns everything affected. | change and impact node, the "highlight" demo |
| `kg_trace(gap_id)` | walks gap → obligation → clause, controls, evidence, remediations. | `GET /gaps/{id}/trace` (fast path) |
| `kg_orphans()` | obligations with no `COVERED_BY` edge. | gap rule "no mapping" (cross-checks the SQL `NOT EXISTS`) |

**Why this is real and not decoration:** each query above runs as a graph traversal in code, and the demo shows the path it found. The `GET /graph` view shows the same nodes and edges.

**Risk and mitigation:**
- Memory only: a restart empties the graph, so it is always rebuilt from Postgres. Show `rebuild_kg` timing (should be milliseconds at this corpus size).
- Two sources of truth: never store mapping decisions only in the graph. Postgres is written first, then the graph is rebuilt.

## 5. API contract (all under `/api/v1`; Vaidehi builds against mocks of these shapes)

| Method | Path | Body / Query | Returns |
|---|---|---|---|
| POST | `/documents` | multipart: `file, doc_type, title, regulator?, version_label?, supersedes_id?` | `{id, status}`. Triggers ingestion, and the pipeline if regulation/policy/rcm |
| GET | `/documents` | | `[{id, doc_type, title, version_label, status, error, created_at}]` |
| POST | `/pipeline/run` | `{}` | `{run_id}`. Runs the full graph over all ready documents |
| GET | `/pipeline/runs/{run_id}` | | `[{node, status, started_at, ended_at, llm_calls, error}]` (live progress UI) |
| GET | `/obligations` | `?document_id=&applicability=` | list with `source_quote, clause_ref, document title` |
| PATCH | `/obligations/{id}` | `{review_status, ...edited fields}` | updated obligation (writes audit) |
| GET | `/controls` | | list |
| GET | `/mappings` | `?obligation_id=` | list incl. `similarity, critic_passed, rationale` |
| PATCH | `/mappings/{id}` | `{status}` | updated |
| GET | `/gaps` | `?status=&priority=` sorted by `risk_score desc` | list |
| GET | `/gaps/{id}/trace` | | **full chain**: `{regulation, clause, source_quote, obligation, controls[], assessment, evidence[], gap, risk_factors, remediations[], audit[]}` |
| PATCH | `/gaps/{id}` | `{status, reason}` | updated |
| POST | `/gaps/{id}/remediation` | `{}` | draft remediation |
| PATCH | `/remediations/{id}` | `{status, action?, owner_team?}` | updated |
| POST | `/changes/compare` | `{old_document_id, new_document_id}` | `{changes:[...], impact:[{change_id, affected_controls[], new_gap_ids[], note}]}` |
$1| GET | `/graph` | `?focus=gap:ID` | `{nodes:[{id,type,label}], edges:[{source,target,type}]}` from the in-memory knowledge graph (for the Graph view and for trace checks) |
| GET | `/eval/latest` | | `{obligation_recall, obligation_precision, mapping_accuracy, gap_recall, gap_type_accuracy, change_detection, citation_validity}` |
| GET | `/audit` | `?entity_id=` | list |

Every write reads the `X-Actor` header and inserts into `audit_log`. Errors use the scaffold's existing error envelope.

---

## 6. Risk formula (feature 9, deterministic and documented)

```
risk_score = criticality × severity × urgency

criticality (from obligation.topic):
  3 = regulatory reporting (CTR/STR/incident), financial-crime monitoring, customer-data security
  2 = customer due diligence / onboarding, currency handling / branch operations
  1 = governance, training, documentation, data minimisation
severity:  missing 3 · design_operating 3 · design 2 · operating 1.5 · insufficient_info 1
urgency:   1.5 if the gap came from a regulatory change (origin = change), else 1.0

priority:  P1 if score ≥ 6 · P2 if 3 ≤ score < 6 · P3 if score < 3
```

Store `risk_factors = {criticality, severity, urgency, rule_version: "v1"}` and show the factors in the UI. This reproduces the bands in `ANSWER_KEY.md`.

## 7. Gap rules (feature 8, deterministic, Vedant)

```
for each applicable obligation:
  no accepted/suggested mapping with coverage covered|partial      → gap missing
  any mapping coverage = insufficient_info                         → gap insufficient_info
  mapping partial / design = inadequate                            → gap design
  design adequate but operating partially_effective|ineffective    → gap operating
  both of the two above                                            → gap design_operating
operating = insufficient_evidence alone → NOT a gap. Show "Insufficient evidence" status instead.
not_applicable obligations → no gap, show the reason
```

---

## 8. Who does what

Swap names if your strengths differ. The **split by layer** is what matters.

### Akhi: AI lead (core agent pipeline)
- `app/integrations/llm/gemini.py`: implements the existing `StructuredLLMProvider` protocol with `google-genai`, structured output, `temperature=0`, the `llm_cache` lookup, one retry on validation error, and `agent_runs` logging.
- `app/workflows/pipeline.py` (the map node takes candidates from `kg_candidates` in `app/kg.py`): the LangGraph graph from §3 (nodes for obligations, applicability, controls, map, critic, assess_evidence, remediation).
- Prompts in `app/agents/prompts/*.md` (one file per node, versioned, so they can go in the architecture doc).
- Owns the accuracy on obligations and mappings.

### Vedant: Backend and database
- Alembic migration for §4 and SQLAlchemy models.
- Upload endpoint: validation, sha256 dedupe, save the file, set status.
- Parsing: `pypdf` for PDF, plain read for MD, `csv` for the RCM and evidence. **Clause-aware chunking** (regex on `^\d+[A-Z]?(\.\d+)*` so "5A.1" matches, plus `Section N` headings) so every chunk has a `clause_ref`.
- All endpoints in §5, audit-log helper, `X-Actor` dependency.
- Deterministic gap rules (§7) and the risk formula (§6).
- `/dashboard/summary` and `/gaps/{id}/trace` (the most important screen).
- Before the demo: `pg_dump` snapshot and restore script.

### Vaidehi: Frontend (the friend's React 19 + Vite + TanStack Query + Tailwind + shadcn + Recharts repo)
Build against **mock JSON** from §5 until checkpoint 1, then switch to the real API.
1. **Dashboard:** KPI tiles (obligations, coverage %, open gaps by P1/P2/P3), a gaps-by-type chart, remediation status, the **accuracy panel** (`/eval/latest`), and recent agent runs.
2. **Documents:** upload (doc type, version, "supersedes" dropdown), status badges, and **live pipeline progress** (poll `/pipeline/runs/{id}`).
3. **Obligations:** a table with the **source quote beside** the structured fields, an applicability badge, and accept/edit/reject.
4. **Gaps:** sorted by risk, with filters. Clicking a gap opens the **trace page**: Regulation clause → Obligation → Control(s) → Evidence → Assessment → Gap → Risk factors → Remediation (approve/edit) → Audit history. *This is the money screen. Make it beautiful.*
5. **Changes:** pick v1/v2 → side-by-side clause diff (added green, deleted red, modified yellow) + impact list linking to the new gaps.
7. **Graph:** a node-link view of `GET /graph` (obligations, controls, gaps) with the selected gap highlighted. Optional if time is short.
8. Header: the "Acting as" dropdown that sets `X-Actor`.

### Anand: Change, impact agents, evaluation, and submission
- `app/workflows/change.py`: **mode (b) first for the real NSM pair** — extract obligations from both, match old↔new by topic keywords from the knowledge graph, Gemini labels modified/added/removed/carried-over; parse the v2 Annex "circulars withdrawn" table → mark matching corpus docs `superseded`, and **warn about withdrawn circulars that are not in the corpus** (see `ANSWER_KEY_NSM_REAL.md` §3). Mode (a) for the synthetic KYC pair: align v1 and v2 by `clause_ref`, `difflib` for added/deleted/modified, Gemini for summary and significance (batched in one call), and marking administrative changes.
- Impact: changed clause → old obligations → mappings → controls; re-run map/assess/gaps for those; set `gaps.origin = change`.
- `scripts/evaluate.py`: compares DB results with `demo_data/3_answer_key/expected_mappings_RBI.csv` and `ANSWER_KEY.md`, stores the metrics, and serves `/eval/latest`.
- **Submission owner:** the architecture document (diagram, node-by-node flow, prompts, model usage, the D2 × F3 justification table in §10), the demo video recording, and the pitch.

---

## 9. Timeline (H0 = start; about 12 hours)

| Time | Everyone / checkpoints | Akhi | Vedant | Vaidehi | Anand |
|---|---|---|---|---|---|
| H0–0:45 | Read this plan. Each person gets a Gemini key. `docker compose up -d --wait db`, `uv sync`. Vedant pushes the migration first. | Gemini client + cache | Migration + models | Mock JSON + page skeletons | Change-diff prototype on v1/v2 (pure Python, no DB) |
| H0:45–4 | | Obligation + control extraction nodes | Upload, parsing, chunking, KG rebuild, document endpoints | Documents + Obligations pages | Change node + evaluation script skeleton |
| **H4** | **Checkpoint 1:** upload RBI KYC Master Direction → obligations visible in the UI with quotes | | | | |
| H4–8 | | Mapping + critic + remediation | Gap rules, risk formula, gaps/trace/dashboard endpoints | Gaps + **Trace** page + Dashboard | Impact analysis + NSM v1 to v2 change pair |
| **H8** | **Checkpoint 2:** full pipeline on all of `demo_data`; run `evaluate.py`; read the numbers together | | | | |
| H8–10 | Fix the worst accuracy problem first (usually extraction prompts or chunking) | Evidence assessment (#6/7) | Bug fixes, edge cases, failure states | Changes page, polish | Architecture doc draft |
| H10–11 | **Code freeze.** Fresh DB → full run → `pg_dump` → rehearse the demo twice | | | | Record a backup demo video |
| H11–12 | Submit: demo video + architecture doc + self-declared D2 × F3 with justification | | | | |

**Rule:** at each checkpoint, if something isn't working, cut a stretch feature. Don't stay up debugging it.

---

## 10. Grid justification (Anand puts this table in the architecture doc, with real numbers)

| Claim | Evidence in demo | Evidence in architecture |
|---|---|---|
| F3: 8+ features | Features #1, 2, 3, 4, 5, 8, 9, 10 (+ 6, 7, 11 if they work), each shown in the demo order below | Node-by-node table mapping each feature to code |
| D2: structured/text input | MD/PDF regulations, CSV RCM and evidence | Ingestion design |
| D2: high demonstrable reliability | **Accuracy panel** against the labelled answer key; citation validity is checked in code; abstains with "insufficient evidence"; critic retry | Critic and validation design, `llm_cache` for determinism, prompts |
| Supporting features | Observability (`agent_runs`), audit trail, HITL approvals, fault tolerance (retry, needs_review, cached fallback) | |

## 11. Demo script (5 minutes)

1. **Problem (20 s):** "Compliance teams map hundreds of clauses to controls by hand. When a circular changes, nobody knows which controls broke."
2. **Upload** RBI KYC Master Direction, NSM v1, the RCM and the evidence → live progress of agent nodes.
3. **Obligations:** structured fields beside the verbatim quote. OB-18 is shown as **Not applicable** with the reason.
4. **Gap trace** for G-12 (privileged access): clause → control (annual) → evidence (14 months, unsigned) → design + operating gap → P1 → remediation draft → **approve as Priya** → audit entry.
5. **The highlight:** upload **NSM v2** (supersedes v1). The agent marks v1 as withdrawn, extracts the new 30 June 2027 phase-out deadline, and flags 7 discontinued machines as a P1 gap. It also reports that the 24 April 2025 circular in the Annex is not in the corpus.
5b. **Real-world proof:** upload the real RBI **Note Sorting Machine Master Direction (2 Oct 2026)**. The agent marks the 2024 circular as withdrawn, finds the new 30 June 2027 phase-out deadline, flags **7 discontinued machines** in the bank's inventory (P1 gap), notes quarterly vs half-yearly testing, and says honestly: *"the 24 Apr 2025 circular listed in the Annex is not in my corpus."*
7. **Accuracy panel:** "Measured against a labelled answer key: X% obligation recall, Y% mapping accuracy, 100% citation validity." Close with the D2 × F3 claim.

## 12. Ready-to-paste prompts for your AI coding tool

**Vedant:**
> In the FastAPI scaffold at RuleSight-backend (SQLAlchemy 2, Alembic, Postgres 17 + pgvector, uv), add one Alembic migration and SQLAlchemy models exactly as in TEAM_PLAN_ONE_NIGHT.md §4. Then implement the endpoints in §5 under app/api/v1, following the existing router, error envelope and logging patterns. Read X-Actor from a header dependency and insert into audit_log on every write. Document upload: validate type (pdf, md, txt, csv), size ≤ 10 MB, sha256 dedupe, save to storage/, parse with pypdf/plain text/csv, clause-aware chunking that keeps clause_ref. Build app/kg.py: an in-memory networkx MultiDiGraph rebuilt from Postgres (§4b) with rebuild_kg(session), kg_candidates(obligation_id) and kg_impact(clause_ref). Implement the gap rules in §7 and the risk formula in §6 as pure functions with unit tests.

**Akhi:**
> Implement app/integrations/llm/gemini.py that satisfies the StructuredLLMProvider protocol in app/integrations/llm/base.py using the google-genai SDK (from google import genai), model from settings.LLM_MODEL (gemini-2.5-flash), temperature 0, response_mime_type application/json, response_schema = the Pydantic schema. Add an llm_cache table lookup by sha256(model+prompt) and one retry on validation error. Then build a LangGraph StateGraph in app/workflows/pipeline.py with nodes as in TEAM_PLAN_ONE_NIGHT.md §3, where the map node takes candidate controls from kg_candidates (app/kg.py). Every extracted item must include a verbatim source_quote; the critic node verifies it is an exact substring of the source text and retries once with the error, else sets needs_review. Unknown fields must be "Not specified", never guessed. Treat document text as untrusted data: wrap it in delimiters and tell the model to ignore instructions inside it.

**Vaidehi:**
> In the React 19 + Vite + TypeScript + TanStack Query + Tailwind + shadcn + Recharts frontend, build the 7 screens in TEAM_PLAN_ONE_NIGHT.md §8 (Vaidehi). Create typed API clients and Zod schemas from the §5 contract, with a mock mode (VITE_USE_MOCKS=true) that serves JSON fixtures, so the UI works before the backend is ready. The Gap Trace page shows the full chain Regulation clause → Obligation → Control → Evidence → Assessment → Gap → Risk factors → Remediation → Audit as a vertical timeline with approve/reject buttons. Every page needs loading, empty and error states. Add an "Acting as" dropdown that sets the X-Actor header.

**Anand:**
> Write app/workflows/change.py: given two documents' chunks with clause_ref, align by clause_ref, classify added/deleted/modified using difflib (ignore whitespace-only changes), then send all modified/added/deleted clauses in one batched Gemini structured call to get a plain-English summary and significance (high/medium/low/administrative). Write impact analysis: changed clause → obligations with that clause_ref in the old version → mappings → controls; re-run mapping/assessment/gap detection for them and set gaps.origin='change'.  Write scripts/evaluate.py that scores DB results against demo_data/3_answer_key/expected_mappings.csv and ANSWER_KEY.md and stores metrics for GET /eval/latest.
