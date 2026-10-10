# Security policy

## Status of this project

RuleSight is a **scaffold under active development**. It has no authentication, no authorisation and
no production hosting yet. Do not expose it to a network, store real data in it, or treat any of its
checks as a security control until those are built and reviewed.

## Reporting a vulnerability

Please report security issues privately. Do not open a public issue or pull request.

- Preferred: GitHub private vulnerability reporting, via the repository's **Security** tab
  ("Report a vulnerability").
- Alternative: contact the maintainers at **[security contact to be configured]**.

Include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof of concept that does not access real data.
- The affected commit or version.

We aim to acknowledge reports within 3 business days and to agree a remediation timeline with you.
Please allow time for a fix before public disclosure.

## Supported versions

Only the `main` branch is supported. There are no released versions yet.

## Handling secrets

- Never commit secrets. Use `.env` files (git-ignored) or a secrets manager.
- `.env.example` files are safe to commit: they contain placeholders only.
- Secret-bearing settings use `SecretStr` and are masked in logs, reprs and error messages.
- If a secret is exposed, rotate it immediately. Removing it from the latest commit is not enough.
- Do not place secrets in `VITE_*` variables. Those are compiled into the public browser bundle.

## Handling data

- Development and tests use **synthetic** data only.
- Real bank, customer or regulator-submitted data must not be pasted into issues, pull requests, logs,
  fixtures or AI prompts.
- Data sent to any external AI provider must be limited to what a task needs, and only after the
  provider's data-retention terms have been approved.

## Hardening already in place

- Security headers on every API response (`nosniff`, `frame-ancestors 'none'`, `no-store`).
- CORS limited to a single configured origin.
- Structured logs with an allow-list of fields. Query strings and request bodies are not logged.
- Error responses contain a safe message and a request ID. Stack traces are logged server-side only.
- Database port bound to `127.0.0.1` in local Docker Compose.
- API documentation disabled when `APP_ENV=production`.
- CI does not use real credentials or real AI keys.

## Known gaps (planned work)

- Authentication and role-based authorisation.
- Rate limiting and request size limits at the edge.
- Dependency and secret scanning in CI.
- Audit log immutability enforced at the database level.
