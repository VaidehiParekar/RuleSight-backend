from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('regulation', 'policy', 'rcm', 'evidence')",
            name="ck_documents_doc_type",
        ),
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready', 'failed', 'superseded')",
            name="ck_documents_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regulator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False)
    withdrawn_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
