"""add business card automation settings and drafts

Revision ID: 20260420_001
Revises: 20260417_001
Create Date: 2026-04-20 12:40:00.000000
"""

from alembic import op


revision = "20260420_001"
down_revision = "20260417_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS businesscardautomationsettings (
            business_id TEXT PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
            news_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            news_interval_hours INTEGER NOT NULL DEFAULT 168,
            news_schedule_mode TEXT NOT NULL DEFAULT 'interval',
            news_schedule_days JSONB,
            news_schedule_time TEXT,
            news_content_source TEXT NOT NULL DEFAULT 'services',
            news_next_run_at TIMESTAMPTZ,
            news_last_run_at TIMESTAMPTZ,
            news_last_status TEXT,
            review_sync_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            review_sync_interval_hours INTEGER NOT NULL DEFAULT 24,
            review_sync_schedule_mode TEXT NOT NULL DEFAULT 'interval',
            review_sync_schedule_days JSONB,
            review_sync_schedule_time TEXT,
            review_sync_next_run_at TIMESTAMPTZ,
            review_sync_last_run_at TIMESTAMPTZ,
            review_sync_last_status TEXT,
            review_reply_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            review_reply_interval_hours INTEGER NOT NULL DEFAULT 24,
            review_reply_trigger TEXT NOT NULL DEFAULT 'schedule',
            review_reply_next_run_at TIMESTAMPTZ,
            review_reply_last_run_at TIMESTAMPTZ,
            review_reply_last_status TEXT,
            digest_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            digest_time TEXT NOT NULL DEFAULT '08:00',
            digest_last_sent_on DATE,
            created_by TEXT,
            updated_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS businesscardautomationevents (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            triggered_by TEXT NOT NULL DEFAULT 'scheduler',
            message TEXT,
            payload_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_businesscardautomationevents_business_created
        ON businesscardautomationevents(business_id, created_at DESC)
        """
    )
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_schedule_mode TEXT NOT NULL DEFAULT 'interval'")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_schedule_days JSONB")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_schedule_time TEXT")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_content_source TEXT NOT NULL DEFAULT 'services'")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_sync_schedule_mode TEXT NOT NULL DEFAULT 'interval'")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_sync_schedule_days JSONB")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_sync_schedule_time TEXT")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_reply_trigger TEXT NOT NULL DEFAULT 'schedule'")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS digest_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS digest_time TEXT NOT NULL DEFAULT '08:00'")
    op.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS digest_last_sent_on DATE")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reviewreplydrafts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            review_id TEXT NOT NULL,
            user_id TEXT,
            source TEXT,
            rating INTEGER,
            author_name TEXT,
            review_text TEXT,
            generated_text TEXT NOT NULL,
            edited_text TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            tone TEXT,
            prompt_key TEXT,
            prompt_version TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewreplydrafts_review_unique
        ON reviewreplydrafts(review_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reviewreplydrafts_business_status
        ON reviewreplydrafts(business_id, status, created_at DESC)
        """
    )
    op.execute(
        """
        ALTER TABLE usernews
        ADD COLUMN IF NOT EXISTS business_id TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_usernews_business_created
        ON usernews(business_id, created_at DESC)
        """
    )


def downgrade():
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS digest_last_sent_on")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS digest_time")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS digest_enabled")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS review_reply_trigger")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS review_sync_schedule_time")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS review_sync_schedule_days")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS review_sync_schedule_mode")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS news_content_source")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS news_schedule_time")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS news_schedule_days")
    op.execute("ALTER TABLE businesscardautomationsettings DROP COLUMN IF EXISTS news_schedule_mode")
    op.execute("DROP INDEX IF EXISTS idx_usernews_business_created")
    op.execute("ALTER TABLE usernews DROP COLUMN IF EXISTS business_id")
    op.execute("DROP INDEX IF EXISTS idx_reviewreplydrafts_business_status")
    op.execute("DROP INDEX IF EXISTS idx_reviewreplydrafts_review_unique")
    op.execute("DROP TABLE IF EXISTS reviewreplydrafts")
    op.execute("DROP INDEX IF EXISTS idx_businesscardautomationevents_business_created")
    op.execute("DROP TABLE IF EXISTS businesscardautomationevents")
    op.execute("DROP TABLE IF EXISTS businesscardautomationsettings")
