"""Enable the pgvector extension (baseline migration).

Revision ID: 0001_enable_pgvector
Revises:
Create Date: 2026-10-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_enable_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Check if the vector extension binary is installed on the PostgreSQL server
    conn = op.get_bind()
    has_vector = conn.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).scalar()

    if has_vector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    else:
        # Gracefully handle standard local PostgreSQL installations that do not have pgvector binaries
        print(
            "Notice: pgvector extension binary is not installed in this PostgreSQL server. "
            "Skipping CREATE EXTENSION vector. Relational domain tables will operate normally."
        )


def downgrade() -> None:
    conn = op.get_bind()
    has_vector = conn.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).scalar()

    if has_vector:
        op.execute("DROP EXTENSION IF EXISTS vector")
