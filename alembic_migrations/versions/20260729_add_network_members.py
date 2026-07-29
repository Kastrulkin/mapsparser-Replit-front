"""add network members

Revision ID: 20260729_001
Revises: 20260727_002
Create Date: 2026-07-29
"""

from alembic import op


revision = "20260729_001"
down_revision = "20260727_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS network_members (
            id TEXT PRIMARY KEY,
            network_id TEXT NOT NULL REFERENCES networks(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'active',
            created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_network_members_role CHECK (role IN ('manager', 'member', 'viewer')),
            CONSTRAINT ck_network_members_status CHECK (status IN ('active', 'revoked')),
            CONSTRAINT uq_network_members_network_user UNIQUE (network_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_network_members_user_active "
        "ON network_members(user_id, network_id) WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_network_members_network_active "
        "ON network_members(network_id, user_id) WHERE status = 'active'"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_network_members_network_active")
    op.execute("DROP INDEX IF EXISTS idx_network_members_user_active")
    op.execute("DROP TABLE IF EXISTS network_members")
