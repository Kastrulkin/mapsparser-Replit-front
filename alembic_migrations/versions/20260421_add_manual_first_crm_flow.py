"""add manual-first crm flow for prospecting leads

Revision ID: 20260421_002
Revises: 20260421_001
Create Date: 2026-04-21 16:10:00.000000
"""

from alembic import op


revision = "20260421_002"
down_revision = "20260421_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS pipeline_status TEXT NOT NULL DEFAULT 'unprocessed'")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS disqualification_reason TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS disqualification_comment TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS postponed_comment TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS next_action_at TIMESTAMPTZ")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_contact_at TIMESTAMPTZ")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_contact_channel TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_contact_comment TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS qualified_at TIMESTAMPTZ")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS qualified_by TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_manual_action_at TIMESTAMPTZ")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS last_manual_action_by TEXT")

    op.execute(
        """
        UPDATE prospectingleads
        SET pipeline_status = CASE
            WHEN COALESCE(status, 'new') = 'new' THEN 'unprocessed'
            WHEN COALESCE(status, '') = 'deferred' THEN 'postponed'
            WHEN COALESCE(status, '') IN ('shortlist_rejected', 'rejected') THEN 'not_relevant'
            WHEN COALESCE(status, '') IN ('sent') THEN 'contacted'
            WHEN COALESCE(status, '') IN ('delivered') THEN 'waiting_reply'
            WHEN COALESCE(status, '') IN ('responded') THEN 'replied'
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
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_pipeline_status
        ON prospectingleads (pipeline_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_next_action_at
        ON prospectingleads (next_action_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_last_contact_at
        ON prospectingleads (last_contact_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            channel_hint TEXT,
            city_hint TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_groups_status
        ON lead_groups (status, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_group_items (
            id TEXT PRIMARY KEY,
            group_id TEXT NOT NULL REFERENCES lead_groups(id) ON DELETE CASCADE,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            added_by TEXT,
            added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (group_id, lead_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_group_items_group_id
        ON lead_group_items (group_id, added_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_group_items_lead_id
        ON lead_group_items (lead_id, added_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_timeline_events (
            id TEXT PRIMARY KEY,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            actor_id TEXT,
            comment TEXT,
            payload_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_timeline_events_lead_created
        ON lead_timeline_events (lead_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_timeline_events_type
        ON lead_timeline_events (event_type, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_lead_timeline_events_type")
    op.execute("DROP INDEX IF EXISTS idx_lead_timeline_events_lead_created")
    op.execute("DROP TABLE IF EXISTS lead_timeline_events")
    op.execute("DROP INDEX IF EXISTS idx_lead_group_items_lead_id")
    op.execute("DROP INDEX IF EXISTS idx_lead_group_items_group_id")
    op.execute("DROP TABLE IF EXISTS lead_group_items")
    op.execute("DROP INDEX IF EXISTS idx_lead_groups_status")
    op.execute("DROP TABLE IF EXISTS lead_groups")
    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_last_contact_at")
    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_next_action_at")
    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_pipeline_status")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS last_manual_action_by")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS last_manual_action_at")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS qualified_by")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS qualified_at")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS last_contact_comment")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS last_contact_channel")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS last_contact_at")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS next_action_at")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS postponed_comment")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS disqualification_comment")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS disqualification_reason")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS pipeline_status")
