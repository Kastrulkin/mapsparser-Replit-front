"""create outreach send batches and queue

Revision ID: 20260302_005
Revises: 20260302_004
Create Date: 2026-03-02 23:35:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260302_005"
down_revision = "20260302_004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreachsendbatches (
            id TEXT PRIMARY KEY,
            batch_date DATE NOT NULL,
            daily_limit INTEGER NOT NULL DEFAULT 10,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT,
            approved_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachsendbatches_batch_date ON outreachsendbatches(batch_date DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachsendbatches_status ON outreachsendbatches(status)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreachsendqueue (
            id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL REFERENCES outreachsendbatches(id) ON DELETE CASCADE,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            draft_id TEXT NOT NULL REFERENCES outreachmessagedrafts(id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'queued',
            provider_message_id TEXT,
            error_text TEXT,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (draft_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachsendqueue_batch_id ON outreachsendqueue(batch_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachsendqueue_delivery_status ON outreachsendqueue(delivery_status)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreachsendqueue_delivery_status")
    op.execute("DROP INDEX IF EXISTS idx_outreachsendqueue_batch_id")
    op.execute("DROP TABLE IF EXISTS outreachsendqueue")
    op.execute("DROP INDEX IF EXISTS idx_outreachsendbatches_status")
    op.execute("DROP INDEX IF EXISTS idx_outreachsendbatches_batch_date")
    op.execute("DROP TABLE IF EXISTS outreachsendbatches")
