from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), nullable=False)
    control_type: Mapped[str] = mapped_column(String(64), nullable=False)
    automation: Mapped[str] = mapped_column(String(64), nullable=False)
    source_document: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    rbi_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
