# Contributing to RuleSight

Thank you for helping. This page covers what you need to start. The full process is in
[docs/development-workflow.md](../docs/development-workflow.md).

## Setup

Follow the setup steps in the [README](README.md). In short: start PostgreSQL with Docker Compose,
install backend dependencies with `uv sync --locked`, and frontend dependencies with `npm ci`.

## Branches

| Prefix | Use for |
| --- | --- |
| `feature/<short-description>` | New functionality |
| `fix/<short-description>` | Bug fixes |
| `docs/<short-description>` | Documentation only |
| `test/<short-description>` | Tests without behaviour change |

Branch from `main`. Pull requests target `main`.

## Commits

`feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `refactor: ...`, `chore: ...`

## Before you open a pull request

- Run the formatters and linters, the type checks, and the tests (commands in
  [docs/development-workflow.md](../docs/development-workflow.md#4-local-checks-before-pushing)).
- Update documentation when behaviour, configuration or setup changes.
- If you changed the schema, follow the migration steps and describe the impact in the PR.
- Keep the pull request focused on one change.

## Reviews and merging

- CI must pass. At least one approving review is required.
- Code owners review their areas once `CODEOWNERS` is configured.
- Do not merge your own pull request unless the repository settings allow it and the change is trivial.

## Formatting and style

- Frontend: Prettier and ESLint (`npm run format`, `npm run lint`). TypeScript is strict. Do not use
  `any`.
- Backend: Ruff for lint and format (`uv run ruff format .`, `uv run ruff check --fix .`). mypy in strict
  mode.
- `.editorconfig` sets encoding, line endings and indentation. Your editor should respect it.

## Hard rules

- **Do not commit** secrets, API keys, passwords, tokens, `.env` files, real bank or customer data,
  or `node_modules/` and `.venv/`.
- **Do not** call paid AI APIs from tests. Mock external services.
- **Do not** add a dependency without a clear need. Say why in the pull request.
- **Do not** add Kubernetes, microservices, Redis, Kafka, or another database without a documented
  requirement.
- **Do not** report security issues in public issues or pull requests. See [SECURITY.md](SECURITY.md).

## Recording decisions

Architecture choices and open questions live in `docs/`. If you make a decision that others will
depend on, add it to the decision log in [docs/architecture.md](../docs/architecture.md).
