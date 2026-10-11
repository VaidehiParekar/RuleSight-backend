import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.kg import rebuild_kg
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import SecurityHeadersMiddleware
from app.db.session import create_engine_for, create_session_factory

logger = logging.getLogger("app.startup")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. Pass explicit settings in tests; production uses get_settings().

    Run with: uvicorn app.main:create_app --factory
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine_for(settings.database_url.get_secret_value())
        app.state.engine = engine
        session_factory = create_session_factory(engine)
        app.state.session_factory = session_factory
        try:
            with session_factory() as session:
                rebuild_kg(session)
        except Exception:
            # The API still starts (the graph is rebuilt on demand), but the failure is visible.
            logger.exception("Could not build the knowledge graph at startup")
        try:
            yield
        finally:
            engine.dispose()

    # Interactive API docs are disabled in production to limit what is exposed publicly.
    is_production = settings.app_env == "production"
    app = FastAPI(
        title="RuleSight API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/api/openapi.json",
    )

    # Middleware runs in reverse order of registration: the last one added is outermost,
    # so request IDs are set before any other layer runs.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")
    return app
