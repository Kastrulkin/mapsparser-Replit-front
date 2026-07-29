"""add business members

Revision ID: 20260729_002
Revises: 20260729_001
Create Date: 2026-07-29
"""

from alembic import op


revision = "20260729_002"
down_revision = "20260729_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS business_members (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'active',
            created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_business_members_role CHECK (role IN ('manager', 'member', 'viewer')),
            CONSTRAINT ck_business_members_status CHECK (status IN ('active', 'revoked')),
            CONSTRAINT uq_business_members_business_user UNIQUE (business_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_business_members_user_active "
        "ON business_members(user_id, business_id) WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_business_members_business_active "
        "ON business_members(business_id, user_id) WHERE status = 'active'"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_business_members_business_active")
    op.execute("DROP INDEX IF EXISTS idx_business_members_user_active")
    op.execute("DROP TABLE IF EXISTS business_members")
