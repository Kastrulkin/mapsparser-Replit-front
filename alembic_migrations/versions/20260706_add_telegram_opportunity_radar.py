"""add telegram opportunity radar

Revision ID: 20260706_001
Revises: 20260701_001
Create Date: 2026-07-06
"""

from alembic import op


revision = "20260706_001"
down_revision = "20260701_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_opportunity_sources (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT,
            account_id TEXT REFERENCES externalbusinessaccounts(id) ON DELETE SET NULL,
            source_type TEXT NOT NULL DEFAULT 'chat',
            title TEXT NOT NULL,
            telegram_chat_id TEXT NOT NULL,
            telegram_username TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            monitor_config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_message_id TEXT,
            last_checked_at TIMESTAMPTZ,
            needs_attention_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (business_id, telegram_chat_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegram_opportunity_sources_business_active
        ON telegram_opportunity_sources (business_id, is_active, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_opportunities (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT,
            source_id TEXT REFERENCES telegram_opportunity_sources(id) ON DELETE SET NULL,
            account_id TEXT REFERENCES externalbusinessaccounts(id) ON DELETE SET NULL,
            telegram_chat_id TEXT NOT NULL,
            telegram_message_id TEXT NOT NULL,
            chat_title TEXT NOT NULL,
            sender_id TEXT,
            message_date TIMESTAMPTZ,
            message_text TEXT NOT NULL DEFAULT '',
            message_link TEXT,
            signal_type TEXT NOT NULL DEFAULT 'other',
            score INTEGER NOT NULL DEFAULT 0,
            reason TEXT,
            reply_draft TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            raw_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            alerted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (business_id, account_id, telegram_chat_id, telegram_message_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegram_opportunities_business_status
        ON telegram_opportunities (business_id, status, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegram_opportunities_source_date
        ON telegram_opportunities (source_id, message_date DESC NULLS LAST)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_opportunity_events (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL REFERENCES telegram_opportunities(id) ON DELETE CASCADE,
            user_id TEXT,
            event_type TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS telegram_opportunity_events")
    op.execute("DROP INDEX IF EXISTS idx_telegram_opportunities_source_date")
    op.execute("DROP INDEX IF EXISTS idx_telegram_opportunities_business_status")
    op.execute("DROP TABLE IF EXISTS telegram_opportunities")
    op.execute("DROP INDEX IF EXISTS idx_telegram_opportunity_sources_business_active")
    op.execute("DROP TABLE IF EXISTS telegram_opportunity_sources")
