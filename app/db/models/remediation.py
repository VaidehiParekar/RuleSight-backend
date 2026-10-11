from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Remediation(Base):
    __tablename__ = "remediations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'in_progress', 'completed', 'verified', 'rejected')",
            name="ck_remediations_status",
        ),
        Index("ix_remediations_gap_id", "gap_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    gap_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("gaps.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    owner_team: Mapped[str] = mapped_column(String(128), nullable=False)
    target_days: Mapped[int] = mapped_column(Integer, nullable=False)
    closure_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
