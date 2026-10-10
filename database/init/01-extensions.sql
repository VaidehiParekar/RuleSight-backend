-- Runs once when the local PostgreSQL volume is first created (docker-entrypoint-initdb.d).
-- The Alembic migration backend/alembic/versions/0001_enable_pgvector.py is the authoritative
-- definition of the extension. This script only makes a fresh local database match it.
CREATE EXTENSION IF NOT EXISTS vector;
