from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegulatoryChange(Base):
    __tablename__ = "changes"
    __table_args__ = (
        CheckConstraint(
            "change_type IN ('modified', 'withdrawn', 'corpus_gap', 'consolidated')",
            name="ck_changes_change_type",
        ),
        CheckConstraint(
            "significance IN ('high', 'medium', 'low', 'administrative')",
            name="ck_changes_significance",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    old_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    new_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    clause_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    old_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    significance: Mapped[str] = mapped_column(String(32), nullable=False)
    carried_over: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    impact: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
