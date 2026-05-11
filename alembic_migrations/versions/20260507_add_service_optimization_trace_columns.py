"""add service optimization trace columns

Revision ID: 20260507_001
Revises: 20260506_002
Create Date: 2026-05-07
"""

from alembic import op


revision = "20260507_001"
down_revision = "20260506_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE userservices ADD COLUMN IF NOT EXISTS fallback_used BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE userservices ADD COLUMN IF NOT EXISTS fallback_reason TEXT")
    op.execute("ALTER TABLE userservices ADD COLUMN IF NOT EXISTS guardrail_reasons JSONB DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE userservices ADD COLUMN IF NOT EXISTS pattern_version_ids JSONB DEFAULT '[]'::jsonb")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_userservices_fallback_used
        ON userservices(fallback_used)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_userservices_fallback_used")
    op.execute("ALTER TABLE userservices DROP COLUMN IF EXISTS pattern_version_ids")
    op.execute("ALTER TABLE userservices DROP COLUMN IF EXISTS guardrail_reasons")
    op.execute("ALTER TABLE userservices DROP COLUMN IF EXISTS fallback_reason")
    op.execute("ALTER TABLE userservices DROP COLUMN IF EXISTS fallback_used")
