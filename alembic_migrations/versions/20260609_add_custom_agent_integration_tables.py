"""add custom agent integration tables

Revision ID: 20260609_002
Revises: 20260609_001
Create Date: 2026-06-09
"""

from alembic import op


revision = "20260609_002"
down_revision = "20260609_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_integrations (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            display_name TEXT,
            auth_ref TEXT,
            config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            connected_by_user_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_integrations_business_provider
        ON agent_integrations(business_id, provider, status)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_trigger_events (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            blueprint_id TEXT,
            run_id TEXT,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            reason_code TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_trigger_events_business_created
        ON agent_trigger_events(business_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_sheet_operation_requests (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL UNIQUE,
            business_id TEXT NOT NULL,
            user_id TEXT,
            integration_id TEXT,
            spreadsheet_id TEXT,
            sheet_name TEXT,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            approval_state TEXT NOT NULL DEFAULT 'pending_human',
            apply_state TEXT NOT NULL DEFAULT 'not_applied',
            row_values_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            mapping_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_event_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            limits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_sheet_operation_requests_business_status
        ON agent_sheet_operation_requests(business_id, status, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_sheet_operation_requests_business_status")
    op.execute("DROP TABLE IF EXISTS agent_sheet_operation_requests")
    op.execute("DROP INDEX IF EXISTS idx_agent_trigger_events_business_created")
    op.execute("DROP TABLE IF EXISTS agent_trigger_events")
    op.execute("DROP INDEX IF EXISTS idx_agent_integrations_business_provider")
    op.execute("DROP TABLE IF EXISTS agent_integrations")
