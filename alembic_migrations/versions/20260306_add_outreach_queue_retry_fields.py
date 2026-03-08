"""add retry/dlq fields to outreachsendqueue

Revision ID: 20260306_001
Revises: 20260305_002
Create Date: 2026-03-06 11:45:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260306_001"
down_revision = "20260305_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS dlq_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreachsendqueue_status_retry
        ON outreachsendqueue(delivery_status, next_retry_at)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreachsendqueue_status_retry")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS dlq_at")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS next_retry_at")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS last_attempt_at")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS attempts")
