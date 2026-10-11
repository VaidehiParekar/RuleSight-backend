"""Audit-trail helpers. The actor always comes from the signed-in user (app.core.deps)."""

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class ActorInfo:
    """Name and role recorded on an audit entry."""

    def __init__(self, name: str, role: str) -> None:
        self.name = name
        self.role = role


def record_audit(
    session: Session,
    actor: ActorInfo,
    action: str,
    entity_type: str,
    entity_code: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> str:
    """Inserts an immutable audit log entry via parameterized SQL."""
    entry_id = f"au-{uuid.uuid4().hex[:8]}"
    query = text("""
        INSERT INTO audit_log (
            id, at, actor, actor_role, action, entity_type, entity_code, reason, before, after
        ) VALUES (
            :id, now(), :actor, :actor_role, :action, :entity_type, :entity_code, :reason,
            CAST(:before AS jsonb), CAST(:after AS jsonb)
        )
    """)
    session.execute(
        query,
        {
            "id": entry_id,
            "actor": actor.name,
            "actor_role": actor.role,
            "action": action,
            "entity_type": entity_type,
            "entity_code": entity_code,
            "reason": reason,
            "before": json.dumps(before) if before is not None else None,
            "after": json.dumps(after) if after is not None else None,
        },
    )
    return entry_id
