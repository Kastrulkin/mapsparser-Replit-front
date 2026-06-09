"""add agent communication delivery journal

Revision ID: 20260609_004
Revises: 20260609_003
Create Date: 2026-06-09
"""

from alembic import op


revision = "20260609_004"
down_revision = "20260609_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_communication_delivery_journal (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            action_id TEXT,
            business_id TEXT NOT NULL,
            run_id TEXT,
            user_id TEXT,
            recipient_key TEXT NOT NULL,
            channel TEXT,
            message_template TEXT,
            status TEXT NOT NULL,
            delivery_state TEXT NOT NULL,
            consent_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            router_handoff_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_communication_delivery_request_recipient
        ON agent_communication_delivery_journal(request_id, recipient_key)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_communication_delivery_business_state
        ON agent_communication_delivery_journal(business_id, delivery_state, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_communication_delivery_business_state")
    op.execute("DROP INDEX IF EXISTS uq_agent_communication_delivery_request_recipient")
    op.execute("DROP TABLE IF EXISTS agent_communication_delivery_journal")
