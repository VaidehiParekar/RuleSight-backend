import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger("app.health")


def is_database_reachable(session: Session) -> bool:
    """Runs a trivial query. Returns False on any database error without exposing its details."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # The driver message can include hostnames or credentials, so it is not logged.
        logger.warning("database readiness check failed")
        return False
    return True
