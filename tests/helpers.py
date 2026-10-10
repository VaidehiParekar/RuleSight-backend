from collections.abc import Iterator
from typing import cast
from unittest.mock import MagicMock

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_session


def make_session(*, reachable: bool) -> Session:
    """Returns a mock session whose SELECT 1 succeeds or fails on demand. No real database."""
    session = MagicMock(spec=Session)
    if reachable:
        session.execute.return_value = None
    else:
        session.execute.side_effect = OperationalError(
            "SELECT 1",
            {},
            Exception("connection refused at 10.0.0.5 as test_user"),
        )
    return cast(Session, session)


def override_session(app: FastAPI, *, reachable: bool) -> None:
    """Replaces the database dependency for the given app instance."""

    def _fake_session() -> Iterator[Session]:
        yield make_session(reachable=reachable)

    app.dependency_overrides[get_session] = _fake_session
