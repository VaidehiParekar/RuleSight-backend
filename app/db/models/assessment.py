from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "design IN ('adequate', 'inadequate', 'unknown')",
            name="ck_assessments_design",
        ),
        CheckConstraint(
            "operating IN ('effective', 'partially_effective', 'ineffective', 'insufficient_evidence', 'not_applicable')",
            name="ck_assessments_operating",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    obligation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("obligations.id", ondelete="CASCADE"), nullable=False
    )
    design: Mapped[str] = mapped_column(String(32), nullable=False)
    design_note: Mapped[str] = mapped_column(Text, nullable=False)
    operating: Mapped[str] = mapped_column(String(32), nullable=False)
    operating_note: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
