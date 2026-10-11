# RuleSight — Regulation, traced.

**Agentic AI for banking regulatory compliance.** RuleSight reads RBI regulations, extracts every
obligation with a word-for-word quote, maps each obligation to a bank's internal controls, finds and
ranks the gaps, drafts fixes for a person to approve, and tracks what changed when RBI replaces a
circular. Every answer carries its source.

Built for the **ET AI Hackathon (Accenture) — Problem Statement 1: agentic AI for banking
regulatory compliance.**

| Repository | Contents |
|---|---|
| **RuleSight-backend** (this repo) | FastAPI API, AI agents (LangGraph + Gemini), PostgreSQL, evaluation |
| **RuleSight-frontend** | React + TypeScript web app (dashboard, gap trace, change view) |

---

## Contents

1. [The problem](#1-the-problem)
2. [What RuleSight does](#2-what-rulesight-does)
3. [Architecture](#3-architecture)
4. [AI models and technologies](#4-ai-models-and-technologies)
5. [Installation and setup](#5-installation-and-setup)
6. [Using the application](#6-using-the-application)
7. [Checking the results](#7-checking-the-results)
8. [API documentation](#8-api-documentation)
9. [Configuration reference](#9-configuration-reference)
10. [Project structure](#10-project-structure)
11. [Tests](#11-tests)
12. [Limitations and future scope](#12-limitations-and-future-scope)
13. [Team](#13-team)

---

## 1. The problem

Banks in India must follow hundreds of RBI rules. Compliance teams read each circular and Master
Direction by hand, work out which internal controls it affects, and try to prove the bank complies.
This is slow and error-prone, and when RBI replaces an old circular nobody knows which controls just
fell out of date. Auditors then ask for the trail: which rule, which control, who signed off.

## 2. What RuleSight does

| # | Feature | How it works | Where in the app |
|---|---|---|---|
| 1 | **Document ingestion** | Upload RBI regulations (PDF/TXT), the bank's risk control matrix and evidence (CSV). Text is extracted and split into numbered RBI paragraphs. | Documents |
| 2 | **Obligation extraction** | Gemini turns each paragraph into structured obligations (who, what, how often, deadline) with a **verbatim quote**. A critic checks the quote in code. | Obligations |
| 3 | **Control framework** | Uploading the risk control matrix (CSV) creates the bank's controls automatically. | Controls |
| 4 | **Regulation → control mapping** | Candidate controls are judged by Gemini (covered / partial / none) with a rationale; the critic verifies codes and quotes. | Gap trace → Controls |
| 5 | **Gap identification** | A deterministic rule tree classifies gaps: missing, design, operating, insufficient info. | Gaps |
| 6 | **Risk prioritisation** | `risk = criticality × severity × urgency` → P1 / P2 / P3. Weights live in `config/risk_rules.json`, not in the AI. | Gap trace → Verdict |
| 7 | **Remediation with human approval** | Gemini drafts a fix; only a Compliance Officer can approve it. Every decision is in the audit log. | Remediation, Audit log |
| 8 | **Change intelligence + impact** | Compares two versions of a regulation, marks the old one as superseded, reads the withdrawal annex, reports withdrawn circulars that are **not** in the corpus, and raises change-driven gaps. | Changes |

Supporting features: role-based access (4 roles), agent-run observability (time, calls and tokens
per step), audit trail, an **accuracy panel measured against a labelled answer key**, LLM response
cache for repeatable runs, and retry with back-off for rate limits.

### Reliability by design
- **Verbatim citations.** Every quote must appear word for word in the source text (checked in code,
  ignoring only whitespace, case and typographic quotes).
- **Generate → check → retry once → flag.** A failed check is sent back to the model once; if it
  still fails, the item is stored as *Needs review*, never silently accepted.
- **Never guess.** Fields the source does not state are "Not specified". Withdrawn circulars that
  are not in the corpus are reported as missing instead of being inferred.
- **Prompt-injection guard.** Document text is wrapped as data in `<source>` blocks; the model is
  told to ignore instructions inside it.
- **Humans decide.** Gaps and fixes are suggestions until a person confirms or approves them.

## 3. Architecture

```
 Browser (React + TypeScript, Vite)
        │  HTTPS / JSON, Authorization: Bearer <JWT>
        ▼
 FastAPI backend ─── role-based access, validation, audit log
        │
        ├── Ingestion: PDF/TXT text extraction → RBI paragraph splitter
        │              RCM CSV → controls, evidence CSV → evidence
        │
        ├── AI pipeline (LangGraph state graph, runs in the background)
        │      extract_obligations ─► map_controls ─► classify gaps (rules) ─► draft_remediation
        │                                                   │
        │                         detect_changes (only when a document supersedes another)
        │      every node: Gemini structured JSON  →  critic (code checks)  →  retry once  →  flag
        │
        ├── Risk rules (config/risk_rules.json) and an in-memory knowledge graph (NetworkX)
        ├── Evaluation: scores each run against the answer key → accuracy panel
        ▼
 PostgreSQL 17 ─── documents, chunks, obligations, controls, mappings, gaps,
                   remediations, changes, agent runs, audit log, users
 File storage  ─── uploaded documents, LLM cache, accuracy report
```

End-to-end flow:
1. A compliance officer signs in and uploads documents.
2. The backend validates the file, stores it and records metadata.
3. **Run pipeline** starts a background run; the UI polls its progress.
4. Agents extract obligations, map controls, classify gaps, draft fixes and, for a new version of a
   regulation, detect changes.
5. Results are stored; the knowledge graph is rebuilt; the run is scored against the answer key.
6. People review gaps, approve fixes, and the audit log records every decision.

## 4. AI models and technologies

| Layer | Technology |
|---|---|
| LLM | **Google Gemini** via `google-genai` (model set in `.env`; tested with `gemini-3.6-flash` and `gemini-3.5-flash-lite`), temperature 0, JSON response schema |
| Agent orchestration | **LangGraph** state graph |
| Validation | Pydantic v2 schemas + a code critic (verbatim quotes, valid codes, rule checks) |
| Knowledge graph | NetworkX (in memory, rebuilt from PostgreSQL) |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PyJWT, bcrypt, pypdf |
| Database | PostgreSQL 17 (pgvector optional, not required) |
| Frontend | React 19, TypeScript, Vite, TanStack Query, React Router, Recharts, Framer Motion |
| Tooling | uv, Ruff, pytest, ESLint, Vitest |

## 5. Installation and setup

### Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | **3.12** | Pinned in `.python-version`; `uv` installs it if missing |
| [uv](https://docs.astral.sh/uv/) | 0.7+ | Python package manager |
| PostgreSQL | 17 | Local install **or** Docker (`docker compose`) |
| Node.js | 22.22+ | For the frontend |
| Gemini API key | — | From [Google AI Studio](https://aistudio.google.com/) |

> **Windows tip:** if `uv sync` tries to build `ormsgpack` with Rust, your machine picked a newer
> Python. Delete `.venv` and run `uv sync --locked` again; `.python-version` pins 3.12
> (`uv python install 3.12` if needed).

### Step 1 — Backend environment

```powershell
cd RuleSight-backend
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```ini
DATABASE_URL=postgresql+psycopg://<user>:<password>@127.0.0.1:5432/<database>
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite          # or another Gemini model your key can use
GEMINI_API_KEY=<your key>
JWT_SECRET_KEY=<random 48+ chars>        # python -c "import secrets; print(secrets.token_urlsafe(48))"
DEMO_USER_PASSWORD=<choose a password>   # applied to the demo accounts in step 4
INSTITUTION_PROFILE=Nova Trust Bank Ltd., a scheduled commercial bank in India
ANSWER_KEY_PATH=./demo_data/3_answer_key/expected_mappings_RBI.csv
LLM_CACHE_DIR=./storage/llm_cache
```

### Step 2 — Database

Either use an existing PostgreSQL 17 database (put its URL in `DATABASE_URL`), or start one with
Docker using the `POSTGRES_*` values in `.env`:

```powershell
docker compose up -d --wait db
```

### Step 3 — Install and migrate

```powershell
uv sync --locked
uv run alembic upgrade head
```

### Step 4 — Set the demo account passwords

The migration creates four demo accounts. Give them the password from `DEMO_USER_PASSWORD`:

```powershell
uv run python scripts/set_user_passwords.py
```

| Email | Role | Can |
|---|---|---|
| `priya@rulesight.bank` | Compliance Officer | Everything: upload, run pipeline, confirm/dismiss gaps, approve fixes |
| `rahul@rulesight.bank` | Compliance Analyst | Upload and review; **cannot** approve or run the pipeline |
| `auditor@rbi.gov.in` | Auditor | Read-only, including the audit log |
| `admin@rulesight.bank` | Admin | Everything, plus user management |

### Step 5 — Run the API

```powershell
uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Check <http://127.0.0.1:8000/api/v1/health/ready> → `{"status":"ready","database":"ok"}`.

### Step 6 — Run the frontend (second terminal)

```powershell
cd RuleSight-frontend
npm ci
npm run dev
```

Open <http://localhost:5173> and sign in. The dev server forwards `/api` to `127.0.0.1:8000`
(change it with `VITE_DEV_API_PROXY_TARGET` in `.env.local`).

## 6. Using the application

All demo inputs are in [`demo_data/`](demo_data/). The RBI documents are real; the bank
(**Nova Trust Bank**) is fictional.

Sign in as **Priya**, open **Documents → Upload document**, and upload in this order:

| # | File (`demo_data/…`) | Type | Notes |
|---|---|---|---|
| 1 | `2_bank_nova_trust/rcm/RCM_Nova_Trust_Risk_Control_Matrix.csv` | RCM | Creates the bank's 11 controls |
| 2 | `2_bank_nova_trust/evidence/EVD-02_…csv`, `EVD-06_…csv`, `EVD-07_…csv` | Evidence | One upload each |
| 3 | `1_regulations_rbi/RBI_KYC_MD_2016_updated_2025-08-14.txt` | Regulation | Regulator: RBI |
| 4 | `1_regulations_rbi/NSM_v1_RBI_circular_2024-10-30_WITHDRAWN.pdf` | Regulation | Regulator: RBI |
| 5 | `1_regulations_rbi/NSM_v2_RBI_Master_Direction_2026-10-02.pdf` | Regulation | **Supersedes: the NSM v1 document** |

Then click **Run pipeline** (Dashboard or Documents). Follow progress under **Agent runs**.
Re-running only processes new documents, so it never duplicates results.

> **Model quota:** the Gemini free tier allows a limited number of requests per day per model.
> If a run reports `429`, wait for the daily reset, switch `LLM_MODEL`, or enable billing.
> Answers are cached in `LLM_CACHE_DIR`, so repeating a run on the same input costs nothing.

What to look at after a run:

| Page | What you see |
|---|---|
| **Dashboard** | Open gaps by priority, coverage, latest run, accuracy panel |
| **Obligations** | Each obligation with its RBI quote and a *Verbatim ✓* badge |
| **Controls** | Controls created from the risk control matrix |
| **Gaps → open a gap** | Full trace: RBI clause → obligation → controls → verdict (risk formula) → remediation → audit |
| **Remediation** | AI-drafted fixes; a Compliance Officer approves or rejects |
| **Changes** | NSM v1 → v2: modified / withdrawn / carried over, and withdrawn circulars not in the corpus |
| **Knowledge graph** | Clauses, obligations, controls and gaps as a graph |
| **Agent runs** | Each agent step's time, model calls, tokens and notes |
| **Audit log** | Who did what, and when |

**Start again from an empty database** (keeps only user accounts):

```powershell
uv run python -m scripts.reset_findings --yes
```

## 7. Checking the results

- **Accuracy panel (Dashboard).** After every run the pipeline scores the stored results against
  `demo_data/3_answer_key/expected_mappings_RBI.csv` (19 obligations, 12 expected gaps). Run it by
  hand with `uv run python -m scripts.evaluate`. Only documents processed by the pipeline are
  scored.
- **Citation validity** re-checks every stored quote against the document text in code.
- **Gap trace** shows the evidence chain for each finding, so a reviewer can verify it in seconds.
- **Answer key** for manual checks: [`demo_data/3_answer_key/ANSWER_KEY.md`](demo_data/3_answer_key/ANSWER_KEY.md)
  and [`ANSWER_KEY_NSM_REAL.md`](demo_data/3_answer_key/ANSWER_KEY_NSM_REAL.md).

Measured on 11 Oct 2026 (KYC paragraphs 3, 6, 18, 37, 38, 46, 68, 70 and NSM v2; model
`gemini-3.5-flash-lite`): citation validity **94%**, applicability **100%**, mapping accuracy **70%**,
obligation recall **50%**, gap recall **25%**. Recall is the main area we are improving (see §12).

## 8. API documentation

Interactive OpenAPI docs: **<http://127.0.0.1:8000/api/docs>** (disabled when `APP_ENV=production`).

All endpoints are under `/api/v1`. Everything except `health` and `auth/login` needs
`Authorization: Bearer <token>`; `401` = not signed in, `403` = role lacks the permission.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me`, `GET /auth/users` (admin) |
| Health | `GET /health`, `GET /health/ready` |
| Documents | `GET /documents`, `GET /documents/{id}`, `POST /documents` (multipart: `file`, `doc_type` = regulation/policy/rcm/evidence, `title`, `regulator`, `version_label`, `supersedes_id`) |
| Pipeline | `POST /pipeline/run` (optional body `{"document_id", "paragraphs": ["37","38"]}`, returns 202), `GET /pipeline/runs`, `GET /pipeline/runs/{id}` |
| Analysis | `GET /obligations`, `PATCH /obligations/{id}`, `GET /controls`, `GET /mappings`, `PATCH /mappings/{id}` |
| Gaps | `GET /gaps`, `GET /gaps/{id}`, `GET /gaps/{id}/trace`, `PATCH /gaps/{id}`, `POST /gaps/{id}/recalculate-risk`, `POST /gaps/{id}/remediation` |
| Remediation | `GET /remediations`, `PATCH /remediations/{id}` |
| Changes | `POST /changes/compare` (`{}` = latest superseding pair), `GET /changes/impact/{clause_ref}` |
| Other | `GET /dashboard/summary`, `GET /graph`, `POST /graph/rebuild`, `GET /audit`, `GET /eval/latest` |

Example:

```powershell
$login = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/auth/login `
  -ContentType 'application/json' -Body '{"email":"priya@rulesight.bank","password":"<password>"}'
Invoke-RestMethod http://127.0.0.1:8000/api/v1/gaps -Headers @{ Authorization = "Bearer $($login.access_token)" }
```

## 9. Configuration reference

All settings come from environment variables / `.env` ([`.env.example`](.env.example) lists every
one with comments). Nothing is hardcoded.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL URL (`postgresql+psycopg://…`) |
| `LLM_PROVIDER`, `LLM_MODEL` (or `GEMINI_MODEL`), `GEMINI_API_KEY` | AI model |
| `LLM_CACHE_DIR` | Cache model answers on disk (repeatable, free re-runs) |
| `LLM_TIMEOUT_SECONDS`, `LLM_TRANSPORT_ATTEMPTS`, `LLM_RETRY_BACKOFF_SECONDS`, `LLM_MIN_INTERVAL_SECONDS` | Timeouts, retries and pacing for rate limits |
| `PIPELINE_MAX_PARAGRAPHS`, `PIPELINE_BATCH_CHARS`, `PIPELINE_RUN_TIMEOUT_MINUTES` | Pipeline size limits |
| `INSTITUTION_PROFILE` | The bank being assessed (used to judge applicability) |
| `RISK_RULES_PATH` | Risk weights and P1/P2 thresholds (`config/risk_rules.json`) |
| `ANSWER_KEY_PATH`, `EVAL_REPORT_PATH` | Automatic accuracy scoring |
| `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES` | Sign-in tokens |
| `DEMO_USER_PASSWORD` | Used only by `scripts/set_user_passwords.py` |
| `STORAGE_DIR`, `MAX_UPLOAD_MB` | Uploaded files |
| `FRONTEND_ORIGIN` | CORS origin of the web app |

## 10. Project structure

```
RuleSight-backend/
├── app/
│   ├── api/v1/          REST endpoints (auth, documents, pipeline, gaps, changes, …)
│   ├── core/            config, auth/JWT, RBAC, risk rules, knowledge graph, logging
│   ├── db/              session and SQL queries
│   ├── integrations/llm Gemini provider (structured output, cache, retries, usage)
│   ├── services/        pipeline runner, change runner, PDF/paragraph parsing,
│   │                    RCM and evidence import, evaluation
│   ├── workflows/       LangGraph pipeline, steps, prompts, schemas, critic, change detection
│   └── main.py          app factory
├── alembic/             database migrations
├── config/risk_rules.json
├── demo_data/           real RBI documents, fictional bank inputs, answer key
├── scripts/             evaluate.py, reset_findings.py, set_user_passwords.py
└── tests/               unit tests (no network, no database)
```

## 11. Tests

```powershell
# Backend (from RuleSight-backend)
uv run pytest -q
uv run ruff check app tests scripts

# Frontend (from RuleSight-frontend)
npx tsc --noEmit
npx eslint . --max-warnings=0
npx vitest run
npx vite build
```

## 12. Limitations and future scope

**Current limitations (honest view)**
- Control matching uses keyword candidates, so some real links are missed; this lowers coverage and
  over-reports "missing control" gaps.
- Evidence files are stored but not yet assessed by the AI (no operating-effectiveness verdicts).
- Gemini free-tier quotas limit how many runs can happen per day.
- No document delete from the UI yet.

**Future scope**
- Ask-a-question over regulations with cited answers (RAG).
- Smarter mapping: judge every obligation against all relevant controls.
- AI evidence review: does the control actually operate, not just exist on paper?
- Watch the RBI website and analyse new circulars automatically; alerts and deadline reminders.
- More regulators (SEBI, IRDAI, FIU-IND), PII redaction, on-premise and multi-bank deployment.

## 13. Team

| Member | Role |
|---|---|
| Akhi | AI pipeline: LangGraph agents, Gemini integration, critic, pipeline runner |
| Vedant | Backend and data: FastAPI, PostgreSQL, role-based access, knowledge graph, risk rules |
| Vaidehi | Frontend: React app, dashboard, gap trace, change view, sign-in |
| Anand | Change intelligence, impact analysis, evaluation, submission |

Licence: see [LICENSE](LICENSE). Security notes: see [SECURITY.md](SECURITY.md).
