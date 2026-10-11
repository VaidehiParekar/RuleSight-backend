"""Create all domain tables via raw SQL queries in migration.

Revision ID: 0002_domain_schema
Revises: 0001_enable_pgvector
Create Date: 2026-10-11

"""

from collections.abc import Sequence
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_domain_schema"
down_revision: str | None = "0001_enable_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id VARCHAR(64) PRIMARY KEY,
        doc_type VARCHAR(32) NOT NULL CHECK (doc_type IN ('regulation', 'policy', 'rcm', 'evidence')),
        title VARCHAR(255) NOT NULL,
        reference VARCHAR(255),
        regulator VARCHAR(64),
        version_label VARCHAR(64) NOT NULL,
        supersedes_id VARCHAR(64) REFERENCES documents(id) ON DELETE SET NULL,
        is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
        file_path VARCHAR(512),
        sha256 VARCHAR(64),
        status VARCHAR(32) NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'ready', 'failed', 'superseded')),
        withdrawn_note TEXT,
        error TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS chunks (
        id VARCHAR(64) PRIMARY KEY,
        document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        clause_ref VARCHAR(64) NOT NULL,
        page INTEGER,
        text TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS obligations (
        id VARCHAR(64) PRIMARY KEY,
        code VARCHAR(32) NOT NULL,
        document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        source_label VARCHAR(128) NOT NULL,
        clause_ref VARCHAR(64) NOT NULL,
        page INTEGER,
        source_quote TEXT NOT NULL,
        key_phrase TEXT,
        quote_verified BOOLEAN NOT NULL DEFAULT FALSE,
        summary TEXT NOT NULL,
        actor VARCHAR(128) NOT NULL,
        action TEXT NOT NULL,
        condition TEXT,
        frequency VARCHAR(64),
        deadline VARCHAR(64),
        threshold VARCHAR(128),
        topic VARCHAR(128) NOT NULL,
        criticality INTEGER NOT NULL CHECK (criticality BETWEEN 1 AND 3),
        applicability VARCHAR(32) NOT NULL CHECK (applicability IN ('applicable', 'not_applicable', 'unknown')),
        applicability_reason TEXT,
        coverage VARCHAR(32) NOT NULL DEFAULT 'none' CHECK (coverage IN ('covered', 'partial', 'none', 'insufficient_info', 'not_applicable')),
        review_status VARCHAR(32) NOT NULL DEFAULT 'suggested' CHECK (review_status IN ('suggested', 'accepted', 'rejected', 'edited')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS controls (
        id VARCHAR(64) PRIMARY KEY,
        code VARCHAR(32) NOT NULL UNIQUE,
        name VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        owner VARCHAR(128) NOT NULL,
        frequency VARCHAR(64) NOT NULL,
        control_type VARCHAR(64) NOT NULL,
        automation VARCHAR(64) NOT NULL,
        source_document VARCHAR(128),
        source_section VARCHAR(64),
        source_quote TEXT,
        evidence_expected TEXT,
        rbi_reference VARCHAR(64),
        topic VARCHAR(128) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS evidence (
        id VARCHAR(64) PRIMARY KEY,
        code VARCHAR(32) NOT NULL UNIQUE,
        title VARCHAR(255) NOT NULL,
        file_name VARCHAR(255) NOT NULL,
        control_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
        columns JSONB NOT NULL DEFAULT '[]'::jsonb,
        rows JSONB NOT NULL DEFAULT '[]'::jsonb,
        flagged_cells JSONB NOT NULL DEFAULT '[]'::jsonb,
        summary TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS mappings (
        id VARCHAR(64) PRIMARY KEY,
        obligation_id VARCHAR(64) NOT NULL REFERENCES obligations(id) ON DELETE CASCADE,
        control_id VARCHAR(64) NOT NULL REFERENCES controls(id) ON DELETE CASCADE,
        coverage VARCHAR(32) NOT NULL CHECK (coverage IN ('covered', 'partial', 'none', 'insufficient_info', 'not_applicable')),
        rationale TEXT NOT NULL,
        graph_path JSONB NOT NULL DEFAULT '[]'::jsonb,
        critic VARCHAR(32) NOT NULL DEFAULT 'passed' CHECK (critic IN ('passed', 'retried', 'failed')),
        status VARCHAR(32) NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested', 'accepted', 'rejected', 'needs_review')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS assessments (
        id VARCHAR(64) PRIMARY KEY,
        obligation_id VARCHAR(64) NOT NULL REFERENCES obligations(id) ON DELETE CASCADE,
        design VARCHAR(32) NOT NULL CHECK (design IN ('adequate', 'inadequate', 'unknown')),
        design_note TEXT NOT NULL,
        operating VARCHAR(32) NOT NULL CHECK (operating IN ('effective', 'partially_effective', 'ineffective', 'insufficient_evidence', 'not_applicable')),
        operating_note TEXT NOT NULL,
        evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS gaps (
        id VARCHAR(64) PRIMARY KEY,
        code VARCHAR(32) NOT NULL UNIQUE,
        obligation_id VARCHAR(64) NOT NULL REFERENCES obligations(id) ON DELETE CASCADE,
        gap_type VARCHAR(32) NOT NULL CHECK (gap_type IN ('missing', 'design', 'operating', 'design_operating', 'insufficient_info')),
        title VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        control_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        origin VARCHAR(32) NOT NULL DEFAULT 'initial' CHECK (origin IN ('initial', 'change')),
        change_id VARCHAR(64),
        risk_factors JSONB NOT NULL DEFAULT '{}'::jsonb,
        risk_score NUMERIC(5, 2) NOT NULL,
        priority VARCHAR(8) NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
        status VARCHAR(32) NOT NULL DEFAULT 'potential' CHECK (status IN ('potential', 'confirmed', 'dismissed', 'needs_info')),
        dismissed_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS remediations (
        id VARCHAR(64) PRIMARY KEY,
        gap_id VARCHAR(64) NOT NULL REFERENCES gaps(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        owner_team VARCHAR(128) NOT NULL,
        target_days INTEGER NOT NULL,
        closure_evidence TEXT NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'in_progress', 'completed', 'verified', 'rejected')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS changes (
        id VARCHAR(64) PRIMARY KEY,
        old_document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        new_document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        clause_ref VARCHAR(64) NOT NULL,
        change_type VARCHAR(32) NOT NULL CHECK (change_type IN ('modified', 'withdrawn', 'corpus_gap', 'consolidated')),
        title VARCHAR(255) NOT NULL,
        old_text TEXT,
        new_text TEXT,
        summary TEXT NOT NULL,
        significance VARCHAR(32) NOT NULL CHECK (significance IN ('high', 'medium', 'low', 'administrative')),
        carried_over JSONB NOT NULL DEFAULT '[]'::jsonb,
        impact JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS missing_circulars (
        id VARCHAR(64) PRIMARY KEY,
        document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        row_num INTEGER NOT NULL,
        reference VARCHAR(255) NOT NULL,
        circular_date VARCHAR(64) NOT NULL,
        subject TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id VARCHAR(64) PRIMARY KEY,
        at TIMESTAMPTZ NOT NULL DEFAULT now(),
        actor VARCHAR(128) NOT NULL,
        actor_role VARCHAR(128) NOT NULL,
        action VARCHAR(128) NOT NULL,
        entity_type VARCHAR(64) NOT NULL,
        entity_code VARCHAR(128) NOT NULL,
        reason TEXT,
        before JSONB,
        after JSONB
    );

    CREATE TABLE IF NOT EXISTS agent_runs (
        id VARCHAR(64) PRIMARY KEY,
        run_id VARCHAR(64) NOT NULL,
        started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        trigger VARCHAR(128) NOT NULL,
        cache_hits INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(32) NOT NULL DEFAULT 'running' CHECK (status IN ('queued', 'running', 'done', 'failed')),
        nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS llm_cache (
        prompt_hash CHAR(64) PRIMARY KEY,
        model VARCHAR(64) NOT NULL,
        response JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS ix_obligations_document_id ON obligations(document_id);
    CREATE INDEX IF NOT EXISTS ix_obligations_applicability ON obligations(applicability);
    CREATE INDEX IF NOT EXISTS ix_obligations_review_status ON obligations(review_status);
    CREATE INDEX IF NOT EXISTS ix_mappings_obligation_id ON mappings(obligation_id);
    CREATE INDEX IF NOT EXISTS ix_mappings_control_id ON mappings(control_id);
    CREATE INDEX IF NOT EXISTS ix_gaps_obligation_id ON gaps(obligation_id);
    CREATE INDEX IF NOT EXISTS ix_gaps_status ON gaps(status);
    CREATE INDEX IF NOT EXISTS ix_gaps_priority ON gaps(priority);
    CREATE INDEX IF NOT EXISTS ix_gaps_risk_score ON gaps(risk_score DESC);
    CREATE INDEX IF NOT EXISTS ix_remediations_gap_id ON remediations(gap_id);
    CREATE INDEX IF NOT EXISTS ix_audit_log_at ON audit_log(at DESC);
    CREATE INDEX IF NOT EXISTS ix_agent_runs_run_id ON agent_runs(run_id);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS llm_cache CASCADE;
    DROP TABLE IF EXISTS agent_runs CASCADE;
    DROP TABLE IF EXISTS audit_log CASCADE;
    DROP TABLE IF EXISTS missing_circulars CASCADE;
    DROP TABLE IF EXISTS changes CASCADE;
    DROP TABLE IF EXISTS remediations CASCADE;
    DROP TABLE IF EXISTS gaps CASCADE;
    DROP TABLE IF EXISTS assessments CASCADE;
    DROP TABLE IF EXISTS mappings CASCADE;
    DROP TABLE IF EXISTS evidence CASCADE;
    DROP TABLE IF EXISTS controls CASCADE;
    DROP TABLE IF EXISTS obligations CASCADE;
    DROP TABLE IF EXISTS chunks CASCADE;
    DROP TABLE IF EXISTS documents CASCADE;
    """)
