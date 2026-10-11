from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Obligation(Base):
    __tablename__ = "obligations"
    __table_args__ = (
        CheckConstraint("criticality BETWEEN 1 AND 3", name="ck_obligations_criticality"),
        CheckConstraint(
            "applicability IN ('applicable', 'not_applicable', 'unknown')",
            name="ck_obligations_applicability",
        ),
        CheckConstraint(
            "coverage IN ('covered', 'partial', 'none', 'insufficient_info', 'not_applicable')",
            name="ck_obligations_coverage",
        ),
        CheckConstraint(
            "review_status IN ('suggested', 'accepted', 'rejected', 'edited')",
            name="ck_obligations_review_status",
        ),
        Index("ix_obligations_document_id", "document_id"),
        Index("ix_obligations_applicability", "applicability"),
        Index("ix_obligations_review_status", "review_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source_label: Mapped[str] = mapped_column(String(128), nullable=False)
    clause_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    key_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(64), nullable=True)
    threshold: Mapped[str | None] = mapped_column(String(128), nullable=True)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    criticality: Mapped[int] = mapped_column(Integer, nullable=False)
    applicability: Mapped[str] = mapped_column(String(32), nullable=False)
    applicability_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="suggested", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
