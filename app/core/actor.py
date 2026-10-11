import json
import uuid
from typing import Annotated, Any
from fastapi import Header, Request
from sqlalchemy import text
from sqlalchemy.orm import Session


class ActorInfo:
    def __init__(self, name: str, role: str) -> None:
        self.name = name
        self.role = role


def get_actor(
    x_actor: Annotated[str | None, Header()] = None,
) -> ActorInfo:
    """Extracts actor details from X-Actor header or falls back to sensible defaults."""
    if not x_actor:
        return ActorInfo(name="Priya Sharma", role="Compliance Officer")
    
    actor_str = x_actor.strip()
    actor_lower = actor_str.lower()
    if "rahul" in actor_lower:
        return ActorInfo(name="Rahul Mehta", role="Analyst")
    if "priya" in actor_lower:
        return ActorInfo(name="Priya Sharma", role="Compliance Officer")
    return ActorInfo(name=actor_str, role="Officer")


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
