"""add parsequeue network batch control columns

Revision ID: 20260308_001
Revises: 20260306_add_outreach_queue_retry_fields
Create Date: 2026-03-08
"""

from alembic import op


revision = "20260308_001"
down_revision = "20260306_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE parsequeue
        ADD COLUMN IF NOT EXISTS batch_id TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE parsequeue
        ADD COLUMN IF NOT EXISTS batch_kind TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE parsequeue
        ADD COLUMN IF NOT EXISTS network_id TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE parsequeue
        ADD COLUMN IF NOT EXISTS batch_seq INTEGER
        """
    )
    op.execute(
        """
        ALTER TABLE parsequeue
        ADD COLUMN IF NOT EXISTS paused_reason TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_parsequeue_batch_id
        ON parsequeue(batch_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_parsequeue_batch_status
        ON parsequeue(batch_id, status)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_parsequeue_batch_status")
    op.execute("DROP INDEX IF EXISTS idx_parsequeue_batch_id")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS paused_reason")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS batch_seq")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS network_id")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS batch_kind")
    op.execute("ALTER TABLE parsequeue DROP COLUMN IF EXISTS batch_id")
