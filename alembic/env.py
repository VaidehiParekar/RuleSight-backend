from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.db.models  # noqa: F401  (registers ORM models on Base.metadata)
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    # Read from the environment via settings. Never hard-code or print the URL.
    return get_settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    """Emits SQL to stdout without connecting. Useful for reviewing migrations."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # The URL is passed as a dict value, not through alembic.ini, so URL-encoded
    # characters in passwords are not mangled by ConfigParser interpolation.
    section = dict(config.get_section(config.config_ini_section, {}))
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
