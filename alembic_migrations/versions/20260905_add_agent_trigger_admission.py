"""add idempotent agent trigger admission and run links

Revision ID: 20260905_004
Revises: 20260905_003
Create Date: 2026-09-05
"""

from alembic import op


revision = "20260905_004"
down_revision = "20260905_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE agent_trigger_events ADD COLUMN IF NOT EXISTS source_event_key TEXT")
    op.execute("ALTER TABLE agent_trigger_events ADD COLUMN IF NOT EXISTS blueprint_version_id TEXT")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_trigger_events_source_key "
        "ON agent_trigger_events(business_id, source, source_event_key) "
        "WHERE source_event_key IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_trigger_run_links (
            id TEXT PRIMARY KEY,
            trigger_event_id TEXT NOT NULL REFERENCES agent_trigger_events(id) ON DELETE CASCADE,
            blueprint_id TEXT NOT NULL,
            blueprint_version_id TEXT NOT NULL,
            run_id TEXT,
            status TEXT NOT NULL,
            reason_code TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (trigger_event_id, blueprint_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_trigger_run_links_event "
        "ON agent_trigger_run_links(trigger_event_id, created_at)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_trigger_run_links_event")
    op.execute("DROP TABLE IF EXISTS agent_trigger_run_links")
    op.execute("DROP INDEX IF EXISTS uq_agent_trigger_events_source_key")
    op.execute("ALTER TABLE agent_trigger_events DROP COLUMN IF EXISTS blueprint_version_id")
    op.execute("ALTER TABLE agent_trigger_events DROP COLUMN IF EXISTS source_event_key")
