"""add provider metadata to outreachreactions

Revision ID: 20260417_001
Revises: 20260416_001
Create Date: 2026-04-17 15:20:00.000000
"""

from alembic import op


revision = "20260417_001"
down_revision = "20260416_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE outreachreactions
        ADD COLUMN IF NOT EXISTS provider_name TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE outreachreactions
        ADD COLUMN IF NOT EXISTS provider_account_id TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE outreachreactions
        ADD COLUMN IF NOT EXISTS provider_message_id TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE outreachreactions
        ADD COLUMN IF NOT EXISTS reply_created_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_outreachreactions_provider_message
        ON outreachreactions(provider_name, provider_account_id, provider_message_id)
        WHERE provider_message_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreachreactions_queue_reply_created
        ON outreachreactions(queue_id, reply_created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreachreactions_queue_reply_created")
    op.execute("DROP INDEX IF EXISTS idx_outreachreactions_provider_message")
    op.execute("ALTER TABLE outreachreactions DROP COLUMN IF EXISTS reply_created_at")
    op.execute("ALTER TABLE outreachreactions DROP COLUMN IF EXISTS provider_message_id")
    op.execute("ALTER TABLE outreachreactions DROP COLUMN IF EXISTS provider_account_id")
    op.execute("ALTER TABLE outreachreactions DROP COLUMN IF EXISTS provider_name")
