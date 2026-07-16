"""add isolated public demo sessions and guided tour progress

Revision ID: 20260716_006
Revises: 20260716_005
Create Date: 2026-07-16 23:30:00.000000
"""

from alembic import op


revision = "20260716_006"
down_revision = "20260716_005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE usersessions
        ADD COLUMN IF NOT EXISTS session_kind TEXT NOT NULL DEFAULT 'standard',
        ADD COLUMN IF NOT EXISTS scope_business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_usersessions_session_kind'
            ) THEN
                ALTER TABLE usersessions
                ADD CONSTRAINT ck_usersessions_session_kind
                CHECK (session_kind IN ('standard', 'demo'));
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guided_tour_progress (
            id UUID PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES usersessions(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            tour_key TEXT NOT NULL,
            tour_version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'not_started',
            chapter_key TEXT,
            step_key TEXT,
            completed_steps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            started_at TIMESTAMPTZ,
            paused_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_guided_tour_progress_status
            CHECK (status IN ('not_started', 'active', 'paused', 'skipped', 'completed')),
            CONSTRAINT uq_guided_tour_progress_session_version
            UNIQUE (session_id, tour_key, tour_version)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_guided_tour_progress_business_status
        ON guided_tour_progress(business_id, tour_key, status, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guided_tour_events (
            id UUID PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES usersessions(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            tour_key TEXT NOT NULL,
            tour_version INTEGER NOT NULL DEFAULT 1,
            event_type TEXT NOT NULL,
            chapter_key TEXT,
            step_key TEXT,
            route TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_guided_tour_events_funnel
        ON guided_tour_events(tour_key, event_type, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_guided_tour_events_funnel")
    op.execute("DROP TABLE IF EXISTS guided_tour_events")
    op.execute("DROP INDEX IF EXISTS idx_guided_tour_progress_business_status")
    op.execute("DROP TABLE IF EXISTS guided_tour_progress")
    op.execute("ALTER TABLE usersessions DROP CONSTRAINT IF EXISTS ck_usersessions_session_kind")
    op.execute("ALTER TABLE usersessions DROP COLUMN IF EXISTS scope_business_id")
    op.execute("ALTER TABLE usersessions DROP COLUMN IF EXISTS session_kind")
