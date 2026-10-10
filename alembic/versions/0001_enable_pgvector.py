"""Enable the pgvector extension (baseline migration).

Revision ID: 0001_enable_pgvector
Revises:
Create Date: 2026-10-10

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_enable_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Required before any vector(n) column exists. The extension is created here, not by hand.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Safe only while no table depends on the vector type. Later migrations must be
    # downgraded first.
    op.execute("DROP EXTENSION IF EXISTS vector")
