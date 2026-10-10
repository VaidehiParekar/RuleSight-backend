# Production-style image for the RuleSight API. Local development normally runs the API on the
# host (see README); this image is for container runs and is started by docker-compose
# under the "app" profile.

FROM python:3.12-slim

# uv is pinned to the same version the team uses locally, so the lockfile resolves identically.
COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Run as an unprivileged user. The application does not need root.
RUN groupadd --system rulesight \
    && useradd --system --gid rulesight --no-create-home --shell /usr/sbin/nologin rulesight

# Install dependencies first so this layer is cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY . .

USER rulesight

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
