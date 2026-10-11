"""Migration tests. These run Alembic against a real PostgreSQL database with pgvector.

They are skipped unless TEST_DATABASE_URL is set. The database must be disposable: the test
drops the vector extension when it downgrades. The name must contain "test" as a guard
against pointing it at a development or production database by mistake.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import get_settings

pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def test_database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")

    database_name = urlparse(url).path.lstrip("/")
    if "test" not in database_name.lower():
        pytest.fail("Refusing to run migrations: TEST_DATABASE_URL must point at a database named *test*")

    # env.py reads DATABASE_URL through settings, so point it at the test database.
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def test_migrations_enable_pgvector_and_downgrade_cleanly(test_database_url: str) -> None:
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    engine = create_engine(test_database_url)
    try:
        command.upgrade(alembic_config, "head")
        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"),
            ).scalar_one_or_none()
        assert version is not None

        command.downgrade(alembic_config, "base")
        with engine.connect() as connection:
            remaining = connection.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'"),
            ).scalar_one()
        assert remaining == 0
    finally:
        engine.dispose()
