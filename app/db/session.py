from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_for(database_url: str) -> Engine:
    """Creates a connection pool. No connection is opened until the first query."""
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    """Per-request session from the factory stored on app.state (no module-level engine).

    Transactions are explicit: services open them with ``session.begin()`` so related
    writes commit or roll back together. This dependency only guarantees the session is closed.
    """
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_session)]


@contextmanager
def write_transaction(session: Session) -> Iterator[Session]:
    """Commits on success and rolls back on any error.

    Works whether or not a read earlier in the request (for example the auth dependency) has
    already started a transaction, which makes ``session.begin()`` raise.
    """
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
