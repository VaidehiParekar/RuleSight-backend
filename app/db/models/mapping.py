from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Mapping(Base):
    __tablename__ = "mappings"
    __table_args__ = (
        CheckConstraint(
            "coverage IN ('covered', 'partial', 'none', 'insufficient_info', 'not_applicable')",
            name="ck_mappings_coverage",
        ),
        CheckConstraint("critic IN ('passed', 'retried', 'failed')", name="ck_mappings_critic"),
        CheckConstraint(
            "status IN ('suggested', 'accepted', 'rejected', 'needs_review')",
            name="ck_mappings_status",
        ),
        Index("ix_mappings_obligation_id", "obligation_id"),
        Index("ix_mappings_control_id", "control_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    obligation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False
    )
    control_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False
    )
    coverage: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    graph_path: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    critic: Mapped[str] = mapped_column(String(32), default="passed", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="suggested", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
