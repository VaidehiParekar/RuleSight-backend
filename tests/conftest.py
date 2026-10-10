from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.main import create_app

# Placeholder credentials for unit tests. No connection is made to this address.
TEST_DATABASE_URL = "postgresql+psycopg://test_user:test_password@127.0.0.1:1/test_db"


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> Iterator[None]:
    """Settings are cached per process. Clear the cache around each test so env changes apply."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    # _env_file=None ignores any local .env, so tests are deterministic on every machine.
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        log_level="WARNING",
        database_url=SecretStr(TEST_DATABASE_URL),
        frontend_origin="http://localhost:5173",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Used without `with`, so the lifespan (which creates a real engine) does not run.
    yield TestClient(app)
