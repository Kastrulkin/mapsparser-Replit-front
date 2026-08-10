"""add founder content editorial loop

Revision ID: 20260810_003_founder
Revises: 20260810_002_roi
Create Date: 2026-08-10
"""

from alembic import op


revision = "20260810_003_founder"
down_revision = "20260810_002_roi"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS founder_content_briefs (
            id UUID PRIMARY KEY,
            content_key TEXT NOT NULL UNIQUE,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            change_summary TEXT NOT NULL,
            rationale TEXT NOT NULL DEFAULT '',
            audience TEXT NOT NULL DEFAULT 'owners_and_operators',
            proof_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            priority INTEGER NOT NULL DEFAULT 50,
            status TEXT NOT NULL DEFAULT 'queued',
            deployed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_founder_content_brief_status CHECK (
                status IN ('queued', 'used', 'skipped', 'blocked')
            ),
            CONSTRAINT ck_founder_content_brief_priority CHECK (
                priority BETWEEN 0 AND 100
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_founder_content_briefs_queue
        ON founder_content_briefs(status, priority DESC, deployed_at DESC NULLS LAST, created_at)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS founder_content_drafts (
            id UUID PRIMARY KEY,
            brief_id UUID NOT NULL REFERENCES founder_content_briefs(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            telegram_id TEXT NOT NULL,
            scheduled_for DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            generated_text TEXT NOT NULL,
            corrected_text TEXT,
            telegram_message_id BIGINT,
            quality_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            diff_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            edit_ratio NUMERIC(6, 5),
            delivered_at TIMESTAMPTZ,
            corrected_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_founder_content_draft_status CHECK (
                status IN ('draft', 'delivered', 'corrected', 'skipped', 'needs_review')
            ),
            CONSTRAINT ck_founder_content_edit_ratio CHECK (
                edit_ratio IS NULL OR edit_ratio BETWEEN 0 AND 1
            ),
            CONSTRAINT uq_founder_content_draft_user_day UNIQUE (user_id, scheduled_for)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_founder_content_draft_telegram_message
        ON founder_content_drafts(telegram_id, telegram_message_id)
        WHERE telegram_message_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_founder_content_drafts_feedback
        ON founder_content_drafts(user_id, status, corrected_at DESC NULLS LAST, delivered_at DESC NULLS LAST)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS founder_content_drafts")
    op.execute("DROP TABLE IF EXISTS founder_content_briefs")
