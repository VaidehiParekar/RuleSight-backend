"""Add RBAC users table and seed default accounts.

Revision ID: 0003_rbac_auth
Revises: 0002_domain_schema
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_rbac_auth"
down_revision: str | None = "0002_domain_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'users'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'role'
        ) THEN
            DROP TABLE users CASCADE;
        END IF;
    END $$;

    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(64) PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        full_name VARCHAR(128) NOT NULL,
        role VARCHAR(32) NOT NULL CHECK (role IN ('admin', 'compliance_officer', 'compliance_analyst', 'auditor')),
        initials VARCHAR(4) NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_login_at TIMESTAMPTZ
    );

    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

    -- Seed baseline demo accounts if not already present
    INSERT INTO users (id, email, hashed_password, full_name, role, initials, is_active, created_at)
    VALUES
        (
            'usr-priya',
            'priya@rulesight.bank',
            '$2b$12$f/gSF9ufAGe.Lm.Scv3JZeRK5LzrI1dm/DZk2d2uHPkOpiHXR/Nje',
            'Priya Sharma',
            'compliance_officer',
            'PS',
            TRUE,
            now()
        ),
        (
            'usr-rahul',
            'rahul@rulesight.bank',
            '$2b$12$WN.i/oHxMYrQ3gIpcezoWuB4kGjVfH2sRpD3oCGpNY8HG6CCyDCe.',
            'Rahul Mehta',
            'compliance_analyst',
            'RM',
            TRUE,
            now()
        ),
        (
            'usr-admin',
            'admin@rulesight.bank',
            '$2b$12$OPPQzodIsn0dQv8QtZAwOuFq3GsTIo9OSqWrmGqUDpLRsAx6b.3wy',
            'System Administrator',
            'admin',
            'SA',
            TRUE,
            now()
        ),
        (
            'usr-auditor',
            'auditor@rbi.gov.in',
            '$2b$12$a4LZgwgvKF3BTG5G7S/bRuFeCFlAkI2n3RPwryyRJo8gFGG7m7vRW',
            'Ananya Sen',
            'auditor',
            'AS',
            TRUE,
            now()
        )
    ON CONFLICT (email) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS users CASCADE;
    """)
