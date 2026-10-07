"""add semantic community topic snapshots

Revision ID: 20260827_001
Revises: 20260826_003
Create Date: 2026-08-27
"""

from alembic import op


revision = "20260827_001"
down_revision = "20260826_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS community_topic_snapshots (
            id UUID PRIMARY KEY,
            source_fingerprint TEXT NOT NULL,
            source_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            period_key TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            period_start TIMESTAMPTZ NOT NULL,
            period_end TIMESTAMPTZ NOT NULL,
            message_count INTEGER NOT NULL DEFAULT 0,
            sample_size INTEGER NOT NULL DEFAULT 0,
            topics_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            analysis_method TEXT NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_community_topic_snapshots_period
                CHECK (period_key IN ('month', 'quarter', 'year')),
            CONSTRAINT ck_community_topic_snapshots_counts
                CHECK (message_count >= 0 AND sample_size >= 0)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_community_topic_snapshots_scope_period
        ON community_topic_snapshots(source_fingerprint, period_key, period_end)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_community_topic_snapshots_latest
        ON community_topic_snapshots(source_fingerprint, generated_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS community_topic_snapshots")
