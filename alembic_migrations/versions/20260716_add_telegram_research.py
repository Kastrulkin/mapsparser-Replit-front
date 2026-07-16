"""add telegram research sync to market knowledge

Revision ID: 20260716_002
Revises: 20260716_001
Create Date: 2026-07-16 15:00:00.000000
"""

from alembic import op


revision = "20260716_002"
down_revision = "20260716_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE knowledge_sources
        ADD COLUMN IF NOT EXISTS business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
        ADD COLUMN IF NOT EXISTS account_id TEXT REFERENCES externalbusinessaccounts(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS sync_mode TEXT NOT NULL DEFAULT 'public_preview',
        ADD COLUMN IF NOT EXISTS sync_status TEXT NOT NULL DEFAULT 'idle',
        ADD COLUMN IF NOT EXISTS backfill_days INTEGER NOT NULL DEFAULT 90,
        ADD COLUMN IF NOT EXISTS backfill_completed_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS next_sync_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS last_sync_error TEXT
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_knowledge_sources_sync_mode'
            ) THEN
                ALTER TABLE knowledge_sources
                ADD CONSTRAINT ck_knowledge_sources_sync_mode
                CHECK (sync_mode IN ('public_preview', 'telegram_userbot', 'archive'));
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_knowledge_sources_sync_status'
            ) THEN
                ALTER TABLE knowledge_sources
                ADD CONSTRAINT ck_knowledge_sources_sync_status
                CHECK (sync_status IN ('idle', 'queued', 'syncing', 'ready', 'partial', 'failed', 'needs_account'));
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_knowledge_sources_backfill_days'
            ) THEN
                ALTER TABLE knowledge_sources
                ADD CONSTRAINT ck_knowledge_sources_backfill_days
                CHECK (backfill_days BETWEEN 1 AND 365);
            END IF;
        END$$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_telegram_sync
        ON knowledge_sources(status, source_type, next_sync_at, last_collected_at)
        WHERE source_type = 'telegram'
        """
    )
    op.execute(
        """
        ALTER TABLE telegram_opportunity_sources
        ADD COLUMN IF NOT EXISTS knowledge_source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE telegram_opportunities
        ADD COLUMN IF NOT EXISTS knowledge_document_id UUID REFERENCES knowledge_documents(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS relevance_score INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS engagement_score INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS priority_score INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegram_opportunities_priority
        ON telegram_opportunities(business_id, priority_score DESC, message_date DESC NULLS LAST)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_telegram_opportunities_priority")
    op.execute("ALTER TABLE telegram_opportunities DROP COLUMN IF EXISTS priority_score")
    op.execute("ALTER TABLE telegram_opportunities DROP COLUMN IF EXISTS engagement_score")
    op.execute("ALTER TABLE telegram_opportunities DROP COLUMN IF EXISTS relevance_score")
    op.execute("ALTER TABLE telegram_opportunities DROP COLUMN IF EXISTS knowledge_document_id")
    op.execute("ALTER TABLE telegram_opportunity_sources DROP COLUMN IF EXISTS knowledge_source_id")
    op.execute("DROP INDEX IF EXISTS idx_knowledge_sources_telegram_sync")
    op.execute("ALTER TABLE knowledge_sources DROP CONSTRAINT IF EXISTS ck_knowledge_sources_backfill_days")
    op.execute("ALTER TABLE knowledge_sources DROP CONSTRAINT IF EXISTS ck_knowledge_sources_sync_status")
    op.execute("ALTER TABLE knowledge_sources DROP CONSTRAINT IF EXISTS ck_knowledge_sources_sync_mode")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS last_sync_error")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS next_sync_at")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS backfill_completed_at")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS backfill_days")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS sync_status")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS sync_mode")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS account_id")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS business_id")
