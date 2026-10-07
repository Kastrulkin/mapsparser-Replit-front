"""optimize paginated lead registry lookups

Revision ID: 20260826_001
Revises: 20260825_002
Create Date: 2026-08-26 10:20:00.000000
"""

from alembic import op


revision = "20260826_001"
down_revision = "20260825_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_enrichment_jobs_workstream_latest
        ON lead_enrichment_jobs(workstream_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreachsendqueue_sent_recipient
        ON outreachsendqueue(
            (LOWER(BTRIM(recipient_value))),
            sent_at DESC,
            updated_at DESC
        )
        WHERE delivery_status IN ('sent', 'delivered')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_inbound_workstream_human
        ON outreach_inbound_events(workstream_id, occurred_at ASC, created_at ASC)
        WHERE is_human = TRUE
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreach_inbound_workstream_human")
    op.execute("DROP INDEX IF EXISTS idx_outreachsendqueue_sent_recipient")
    op.execute("DROP INDEX IF EXISTS idx_lead_enrichment_jobs_workstream_latest")
