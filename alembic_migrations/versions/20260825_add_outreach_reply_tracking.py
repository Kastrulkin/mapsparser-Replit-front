"""track manual outreach conversations and external CRM tasks

Revision ID: 20260825_002
Revises: 20260825_001
Create Date: 2026-08-25 17:30:00.000000
"""

from alembic import op


revision = "20260825_002"
down_revision = "20260825_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_thread_bindings (
            id UUID PRIMARY KEY,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            workstream_id UUID NOT NULL REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            sender_account_id UUID NOT NULL REFERENCES outreach_sender_accounts(id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            external_thread_id TEXT,
            external_peer_id TEXT NOT NULL,
            last_processed_event_id TEXT,
            last_processed_at TIMESTAMPTZ,
            status TEXT NOT NULL DEFAULT 'active',
            binding_source TEXT NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_thread_binding_channel
                CHECK (channel IN ('email', 'telegram', 'vk')),
            CONSTRAINT ck_outreach_thread_binding_status
                CHECK (status IN ('active', 'paused', 'ambiguous', 'revoked')),
            CONSTRAINT ck_outreach_thread_binding_source
                CHECK (binding_source IN ('contact_match', 'sent_message', 'manual', 'history_backfill'))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_thread_binding_active_peer
        ON outreach_thread_bindings(
            sender_account_id, channel, external_peer_id
        ) WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_thread_binding_workstream
        ON outreach_thread_bindings(workstream_id, status, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_thread_binding_poll
        ON outreach_thread_bindings(channel, sender_account_id, status, last_processed_at)
        WHERE status = 'active'
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_external_task_bindings (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            workstream_id UUID NOT NULL REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            external_task_id TEXT NOT NULL,
            external_url TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_synced_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_external_task_provider CHECK (provider IN ('yougile')),
            CONSTRAINT ck_outreach_external_task_status CHECK (status IN ('active', 'archived')),
            UNIQUE(provider, external_task_id),
            UNIQUE(workstream_id, provider)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_external_task_business
        ON outreach_external_task_bindings(business_id, provider, status)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreach_external_task_business")
    op.execute("DROP TABLE IF EXISTS outreach_external_task_bindings")
    op.execute("DROP INDEX IF EXISTS idx_outreach_thread_binding_poll")
    op.execute("DROP INDEX IF EXISTS idx_outreach_thread_binding_workstream")
    op.execute("DROP INDEX IF EXISTS uq_outreach_thread_binding_active_peer")
    op.execute("DROP TABLE IF EXISTS outreach_thread_bindings")
