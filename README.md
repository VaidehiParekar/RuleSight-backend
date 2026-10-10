# RuleSight

AI-assisted regulatory compliance intelligence for banks. RuleSight helps compliance teams read regulations,
extract obligations, map them to controls and policies, assess evidence, find gaps, and track remediation.
The AI proposes; people approve. Every consequential decision is recorded in an audit trail.

> **Status: scaffold.** The repository currently contains a working development foundation: a web shell,
> a versioned API with health checks, database migrations, CI, and documentation. **No compliance feature
> is implemented yet.** See [What works today](#what-works-today) and [Planned](#planned).

## Stack

| Layer | Technology |
| --- | --- |
| Web app | React 19, TypeScript (strict), Vite 8, React Router 8, TanStack Query 5, Tailwind CSS 4, shadcn/ui-style components, Zod, React Hook Form, Recharts |
| API | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, psycopg 3 |
| Database | PostgreSQL 17 with pgvector |
| AI (planned) | Gemini through a provider interface, LangGraph for controlled workflows, a configurable embedding provider |
| Tooling | uv, npm, Ruff, mypy, pytest, Vitest, React Testing Library, ESLint, Prettier, Docker Compose, GitHub Actions |

## What works today

| Area | Status |
| --- | --- |
| Web app shell with navigation, skip link, and accessible loading, empty, error and success states | Implemented |
| Dashboard placeholder that checks API readiness (clearly labelled as scaffold) | Implemented |
| Feature routes for every planned area | Placeholder pages stating "not implemented" |
| `GET /api/v1/health` (liveness) and `GET /api/v1/health/ready` (database check) | Implemented |
| Typed configuration from environment variables, secrets masked | Implemented |
| Error envelope with request IDs, validation errors without echoed input | Implemented |
| JSON logs, request-ID propagation, security headers, CORS to one origin | Implemented |
| Alembic migrations (baseline enables pgvector) | Implemented |
| Docker Compose PostgreSQL + pgvector with health check | Implemented (not run in this environment; see [Troubleshooting](#troubleshooting)) |
| CI: frontend lint, types, tests, build; backend Ruff, mypy, unit and integration tests | Implemented (defined; first run pending) |
| Authentication and authorisation | **Not implemented** |
| Domain tables, document ingestion, retrieval, AI agents | **Not implemented** |

## Planned

Ordered by dependency. Each item needs its own design note before it is built.

1. Authentication and roles, since every later endpoint depends on them.
2. Organisations, users, and the audit event table (append-only).
3. Regulatory sources, regulation versions and obligations.
4. Document upload with immutable versions, chunking with provenance, and embeddings (pgvector).
5. Retrieval service with citations.
6. Controls, policies, and mappings.
7. Evidence, control tests, and assessment runs.
8. Gap identification and risk prioritisation, once scoring rules are specified.
9. Remediation tasks and AI-assisted recommendations, with human approval checkpoints.

Details are in [docs/architecture.md](../docs/architecture.md), [docs/database-design.md](../docs/database-design.md) and
[docs/ai-architecture.md](../docs/ai-architecture.md).

## Repository layout

```
RuleSight/
  frontend/   React web app (Vite). Its own Git repository.
  backend/    This repository: FastAPI API, AI agents, Alembic migrations, tests,
              database/ (Docker init SQL, seed-data policy), infra/, scripts/,
              docker-compose.yml, Makefile, CI workflow, and project policy files.
  docs/       Architecture, database design, AI architecture, development workflow
  .claude/    Local Claude Code settings (not committed)
```

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Node.js | 24 LTS recommended, minimum 22.22.2 | CI uses 24. Older 22.x versions print engine warnings and may fail. |
| Python | 3.12 or newer | `uv` can install it for you. |
| uv | 0.7.3 | Matches the Dockerfile and CI. Install from <https://docs.astral.sh/uv/>. |
| Docker Desktop | Recent | Runs PostgreSQL and optional API container. |
| Git | 2.40+ | |

## Setup (Windows PowerShell)

Run from the `backend` folder (`RuleSight\backend`) unless a step says otherwise.

```powershell
# 1. Create local environment files from the templates. These files are git-ignored.
#    backend/.env holds both the API settings and the local PostgreSQL settings for docker compose.
Copy-Item .env.example .env
Copy-Item ..\frontend\.env.example ..\frontend\.env.local

# 2. Start PostgreSQL with pgvector. Wait until the health check passes.
docker compose up -d --wait db

# 3. Backend: install from the lockfile, then apply migrations.
uv sync --locked
uv run alembic upgrade head

# 4. Run the API (leave this terminal open).
uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
# 5. Frontend: install from the lockfile, then start the dev server.
cd D:\Documents\RuleSight\frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The dashboard should show "API is ready" and "Connected".

Check the API directly: <http://127.0.0.1:8000/api/v1/health> and <http://127.0.0.1:8000/api/v1/health/ready>.
Interactive API docs are at <http://127.0.0.1:8000/api/docs> when `APP_ENV` is not `production`.

### Optional: run the API in Docker

```powershell
docker compose --profile app up -d --build
```

This builds `Dockerfile` in this folder. Run migrations against the containerised database with
`docker compose exec api alembic upgrade head`.

### Stop and reset

```powershell
docker compose down            # stop, keep data
docker compose down -v         # stop and DELETE the local database volume
```

## Configuration

Configuration is read from environment variables. Each component has an `.env.example` with descriptions.

| Variable | Where | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | backend | SQLAlchemy URL with the `postgresql+psycopg://` scheme. Required. |
| `APP_ENV` | backend | `development`, `test` or `production`. Production disables API docs. |
| `LOG_LEVEL` | backend | `DEBUG` to `CRITICAL`. Default `INFO`. |
| `FRONTEND_ORIGIN` | backend | The one browser origin allowed by CORS. |
| `LLM_PROVIDER`, `LLM_MODEL` | backend | Language model selection. Default `none`: no external call. |
| `EMBEDDING_PROVIDER` | backend | Embedding selection. Default `none`. |
| `GEMINI_API_KEY` | backend | Secret. Needed only when `LLM_PROVIDER=gemini`. Never commit it. |
| `VITE_API_BASE_URL` | frontend | API base path or URL. Default `/api/v1`. Validated at startup. |
| `VITE_DEV_API_PROXY_TARGET` | frontend | Development only: where `/api` is forwarded. Default `http://127.0.0.1:8000`. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT` | root (`.env`) | Local Compose database. The password is a placeholder. |

Rules:

- `.env` files are git-ignored. `.env.example` files are committed and must contain placeholders only.
- Do not put secrets in `VITE_*` variables. They are published in the browser bundle.
- The API never prints configuration values. Secret fields are masked in reprs and errors.

## Tests and checks

Windows PowerShell:

```powershell
# Backend unit tests (no database needed)
uv run pytest -m "not integration"

# Backend lint, format check and type check
uv run ruff check .
uv run ruff format --check .
uv run mypy

# Integration tests: need a disposable database whose name contains "test".
docker compose exec db createdb -U rulesight rulesight_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://rulesight:change-me-local-only@127.0.0.1:5432/rulesight_test"
uv run pytest -m integration
Remove-Item Env:TEST_DATABASE_URL

# Frontend
cd ..\frontend
npm test
npm run lint
npm run typecheck
npm run format:check
npm run build
```

Formatting fixes: `uv run ruff format .` and `npm run format` (both write files).

On macOS or Linux, `make check` runs everything (see the [Makefile](Makefile)). `make` is not installed by
default on Windows, so use the commands above there.

### Creating a migration

```powershell
uv run alembic revision --autogenerate -m "describe the change"
# Read and edit the generated file, then:
uv run alembic upgrade head
```

See [docs/development-workflow.md](../docs/development-workflow.md#5-database-migrations).

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `Invalid frontend configuration: VITE_API_BASE_URL: ...` | The value must be a path starting with `/` or an `http(s)://` URL. |
| Dashboard says "API is not reachable" | The API is not running, or it is on a different port. Check the backend terminal. |
| Dashboard says "The database is unavailable" | Start the database with `docker compose up -d --wait db`, then retry. |
| `ValidationError ... DATABASE_URL must use the postgresql+psycopg:// scheme` | Change the scheme in `backend/.env`. |
| `docker compose` says a variable is required | Create `backend/.env` from `.env.example`. |
| Port 5432 or 8000 already in use | Set `POSTGRES_PORT` in `.env`, or stop the other process. |
| `npm ci` prints `EBADENGINE` | Your Node.js is older than 22.22.2. Upgrade to Node 24 LTS. |
| `make: command not found` on Windows | Use the PowerShell commands above. Make is optional. |
| Install fails with `ENOSPC: no space left on device` | The drive holding the npm or uv cache is full. Free space, or point the cache at another drive with `npm install --cache <path>` or `UV_CACHE_DIR`. |
| Integration tests are skipped | `TEST_DATABASE_URL` is not set. This is expected locally unless you set it. |
| Integration tests refuse to run | The database name must contain `test`. This guard prevents migrations on a development database. |

## Contributing and security

- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy and vulnerability reporting: [SECURITY.md](SECURITY.md)
- CODEOWNERS template: [CODEOWNERS.example](CODEOWNERS.example)

## Licence

Not yet decided. All rights are reserved for now; see [LICENSE](LICENSE).
