from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceProvenance(BaseModel):
    """Where a retrieved passage came from. Every citation must carry this."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: UUID
    document_version_id: UUID
    page_number: int | None = Field(default=None, ge=1)
    section_path: str | None = None


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: UUID
    text: str
    similarity: float = Field(ge=0.0, le=1.0)
    provenance: SourceProvenance


class Retriever(Protocol):
    """Contract for the retrieval service. Implementations live in this package (planned)."""

    def search(self, query: str, *, limit: int) -> list[RetrievedChunk]:
        """Returns up to ``limit`` chunks ordered by descending similarity, each with provenance."""
        ...
