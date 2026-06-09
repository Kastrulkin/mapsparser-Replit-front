"""add agent domain request tables

Revision ID: 20260609_001
Revises: 20260525_001
Create Date: 2026-06-09
"""

from alembic import op


revision = "20260609_001"
down_revision = "20260525_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_communication_requests (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL UNIQUE,
            business_id TEXT NOT NULL,
            user_id TEXT,
            capability TEXT NOT NULL,
            message_type TEXT NOT NULL,
            status TEXT NOT NULL,
            channel TEXT,
            recipient_count INTEGER NOT NULL DEFAULT 0,
            recipients_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            message_template TEXT,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            consent_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            delivery_state TEXT NOT NULL DEFAULT 'not_dispatched',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_communication_requests_business_status
        ON agent_communication_requests(business_id, status, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_service_optimization_requests (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL UNIQUE,
            business_id TEXT NOT NULL,
            user_id TEXT,
            status TEXT NOT NULL,
            service_count INTEGER NOT NULL DEFAULT 0,
            suggestions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            apply_state TEXT NOT NULL DEFAULT 'not_applied',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_service_optimization_requests_business_status
        ON agent_service_optimization_requests(business_id, status, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_service_optimization_requests_business_status")
    op.execute("DROP TABLE IF EXISTS agent_service_optimization_requests")
    op.execute("DROP INDEX IF EXISTS idx_agent_communication_requests_business_status")
    op.execute("DROP TABLE IF EXISTS agent_communication_requests")
