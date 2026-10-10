"""ORM models. Import every model module here so Alembic autogenerate can see the full metadata.

No domain tables exist yet. They are added with their features, following docs/database-design.md.
"""

from app.db.base import Base

__all__ = ["Base"]
