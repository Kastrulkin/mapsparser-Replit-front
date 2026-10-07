"""Move bounded prospecting runtime schema work into Alembic.

Revision ID: 20260906_011
Revises: 20260906_010
"""

from alembic import op


revision = "20260906_011"
down_revision = "20260906_010"
branch_labels = None
depends_on = None


def upgrade():
    # 20260421_002 owns the manual CRM columns and lead-group tables. This
    # one-time reconciliation keeps statuses introduced after that migration.
    op.execute(
        """
        UPDATE prospectingleads
        SET pipeline_status = CASE
            WHEN COALESCE(status, 'new') = 'new' THEN 'unprocessed'
            WHEN COALESCE(status, '') = 'deferred' THEN 'postponed'
            WHEN COALESCE(status, '') IN ('shortlist_rejected', 'rejected') THEN 'not_relevant'
            WHEN COALESCE(status, '') = 'sent' THEN 'contacted'
            WHEN COALESCE(status, '') = 'delivered' THEN 'waiting_reply'
            WHEN COALESCE(status, '') = 'responded' THEN 'replied'
            WHEN COALESCE(status, '') = 'second_message_sent' THEN 'second_message_sent'
            WHEN COALESCE(status, '') IN ('qualified', 'converted') THEN 'converted'
            WHEN COALESCE(status, '') = 'closed' THEN 'closed_lost'
            ELSE 'in_progress'
        END
        WHERE COALESCE(pipeline_status, '') = ''
           OR (COALESCE(pipeline_status, '') = 'unprocessed' AND COALESCE(status, 'new') <> 'new')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS partnershipleadartifacts (
            lead_id TEXT PRIMARY KEY REFERENCES prospectingleads(id) ON DELETE CASCADE,
            audit_json JSONB,
            match_json JSONB,
            offer_draft_json JSONB,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade():
    # Audit and match artifacts are durable review evidence.
    pass
