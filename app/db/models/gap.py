from datetime import datetime
from typing import Any
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Gap(Base):
    __tablename__ = "gaps"
    __table_args__ = (
        CheckConstraint(
            "gap_type IN ('missing', 'design', 'operating', 'design_operating', 'insufficient_info')",
            name="ck_gaps_gap_type",
        ),
        CheckConstraint("origin IN ('initial', 'change')", name="ck_gaps_origin"),
        CheckConstraint("priority IN ('P1', 'P2', 'P3')", name="ck_gaps_priority"),
        CheckConstraint(
            "status IN ('potential', 'confirmed', 'dismissed', 'needs_info')",
            name="ck_gaps_status",
        ),
        Index("ix_gaps_obligation_id", "obligation_id"),
        Index("ix_gaps_status", "status"),
        Index("ix_gaps_priority", "priority"),
        Index("ix_gaps_risk_score", "risk_score"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    obligation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False
    )
    gap_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    control_ids: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    origin: Mapped[str] = mapped_column(String(32), default="initial", nullable=False)
    change_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_factors: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}", nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    priority: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="potential", nullable=False)
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
