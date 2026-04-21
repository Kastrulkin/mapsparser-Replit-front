"""add bot feature requests table

Revision ID: 20260421_001
Revises: 20260420_001
Create Date: 2026-04-21 11:40:00.000000
"""

from alembic import op


revision = "20260421_001"
down_revision = "20260420_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS botfeaturerequests (
            id TEXT PRIMARY KEY,
            telegram_id TEXT NOT NULL,
            user_id TEXT NULL,
            business_id TEXT NULL,
            source TEXT NOT NULL DEFAULT 'telegram_bot',
            category TEXT NOT NULL DEFAULT 'other',
            request_text TEXT NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_botfeaturerequests_created
        ON botfeaturerequests (created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_botfeaturerequests_business
        ON botfeaturerequests (business_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_botfeaturerequests_status
        ON botfeaturerequests (status, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_botfeaturerequests_status")
    op.execute("DROP INDEX IF EXISTS idx_botfeaturerequests_business")
    op.execute("DROP INDEX IF EXISTS idx_botfeaturerequests_created")
    op.execute("DROP TABLE IF EXISTS botfeaturerequests")
