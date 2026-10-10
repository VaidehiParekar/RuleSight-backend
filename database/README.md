# Database assets

| Path | Purpose |
| --- | --- |
| `init/` | SQL run once when a new local PostgreSQL volume is created (extensions only). |
| `seed/` | Future **synthetic** development seed data. Never real bank, customer or regulator-submitted data. |

Schema changes are made only through Alembic migrations in `backend/alembic/versions/`, never by
editing a database by hand. The logical model is in [docs/database-design.md](../../docs/database-design.md).

Seed data, when added, must be generated, clearly labelled as synthetic, and loaded by an explicit
command. It must never run automatically in production.
