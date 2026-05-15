"""add agent api security tables

Revision ID: 20260514_001
Revises: 20260512_001
Create Date: 2026-05-14
"""

from alembic import op


revision = "20260514_001"
down_revision = "20260512_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_clients (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            organization_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'sandbox',
            allowed_scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
            rate_limits JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_action_ledger (
            id TEXT PRIMARY KEY,
            agent_client_id TEXT,
            business_id TEXT,
            action_type TEXT NOT NULL,
            capability TEXT,
            required_scope TEXT,
            risk_level TEXT NOT NULL,
            input_summary TEXT,
            output_summary TEXT,
            approval_id TEXT,
            status TEXT NOT NULL,
            reason_code TEXT,
            ip TEXT,
            user_agent TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_discovery_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            path TEXT NOT NULL,
            method TEXT NOT NULL,
            status_code INT,
            agent_family TEXT NOT NULL DEFAULT 'unknown',
            ip_hash TEXT,
            user_agent TEXT,
            referrer TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_clients_key_hash ON agent_clients(key_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_clients_owner ON agent_clients(owner_user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_clients_status ON agent_clients(status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_client_created ON agent_action_ledger(agent_client_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_business_created ON agent_action_ledger(business_id, created_at DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_risk ON agent_action_ledger(risk_level, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_action_ledger_status ON agent_action_ledger(status, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_discovery_events_created ON agent_discovery_events(created_at DESC)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_discovery_events_family_created ON agent_discovery_events(agent_family, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_discovery_events_type_created ON agent_discovery_events(event_type, created_at DESC)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_discovery_events_type_created")
    op.execute("DROP INDEX IF EXISTS idx_agent_discovery_events_family_created")
    op.execute("DROP INDEX IF EXISTS idx_agent_discovery_events_created")
    op.execute("DROP INDEX IF EXISTS idx_agent_action_ledger_status")
    op.execute("DROP INDEX IF EXISTS idx_agent_action_ledger_risk")
    op.execute("DROP INDEX IF EXISTS idx_agent_action_ledger_business_created")
    op.execute("DROP INDEX IF EXISTS idx_agent_action_ledger_client_created")
    op.execute("DROP INDEX IF EXISTS idx_agent_clients_status")
    op.execute("DROP INDEX IF EXISTS idx_agent_clients_owner")
    op.execute("DROP INDEX IF EXISTS uq_agent_clients_key_hash")
    op.execute("DROP TABLE IF EXISTS agent_discovery_events")
    op.execute("DROP TABLE IF EXISTS agent_action_ledger")
    op.execute("DROP TABLE IF EXISTS agent_clients")
