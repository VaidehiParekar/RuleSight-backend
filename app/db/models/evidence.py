from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    control_codes: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    columns: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    rows: Mapped[list[list[str]]] = mapped_column(JSONB, server_default="[]", nullable=False)
    flagged_cells: Mapped[list[list[int]]] = mapped_column(JSONB, server_default="[]", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
