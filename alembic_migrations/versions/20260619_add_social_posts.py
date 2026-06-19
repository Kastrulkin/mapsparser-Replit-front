"""add social posts for content plans

Revision ID: 20260619_001
Revises: 20260618_001
Create Date: 2026-06-19 12:00:00.000000
"""

from alembic import op


revision = "20260619_001"
down_revision = "20260618_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS social_posts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            content_plan_id TEXT NOT NULL REFERENCES contentplans(id) ON DELETE CASCADE,
            content_plan_item_id TEXT NOT NULL REFERENCES contentplanitems(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            publish_mode TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            scheduled_for TIMESTAMPTZ,
            approved_at TIMESTAMPTZ,
            published_at TIMESTAMPTZ,
            base_text TEXT,
            platform_text TEXT,
            media_json JSONB NOT NULL DEFAULT '[]',
            external_account_id TEXT,
            provider_post_id TEXT,
            provider_post_url TEXT,
            approval_id TEXT,
            automation_task_id TEXT,
            last_error TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_social_posts_platform CHECK (
                platform IN ('yandex_maps', 'two_gis', 'google_business', 'telegram', 'vk', 'instagram', 'facebook')
            ),
            CONSTRAINT chk_social_posts_publish_mode CHECK (
                publish_mode IN ('api', 'openclaw_browser', 'local_supervised_browser', 'manual')
            ),
            CONSTRAINT chk_social_posts_status CHECK (
                status IN (
                    'draft',
                    'needs_review',
                    'approved',
                    'queued',
                    'publishing',
                    'published',
                    'failed',
                    'needs_manual_publish',
                    'needs_supervised_publish'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_social_posts_item_platform
        ON social_posts (content_plan_item_id, platform)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_social_posts_plan_status
        ON social_posts (content_plan_id, status, scheduled_for)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_social_posts_business_platform
        ON social_posts (business_id, platform, status)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS social_post_metrics (
            id TEXT PRIMARY KEY,
            social_post_id TEXT NOT NULL REFERENCES social_posts(id) ON DELETE CASCADE,
            metric_date DATE NOT NULL,
            views INTEGER NOT NULL DEFAULT 0,
            impressions INTEGER NOT NULL DEFAULT 0,
            reach INTEGER NOT NULL DEFAULT 0,
            likes INTEGER NOT NULL DEFAULT 0,
            comments INTEGER NOT NULL DEFAULT 0,
            shares INTEGER NOT NULL DEFAULT 0,
            clicks INTEGER NOT NULL DEFAULT 0,
            inquiries INTEGER NOT NULL DEFAULT 0,
            leads INTEGER NOT NULL DEFAULT 0,
            raw_json JSONB NOT NULL DEFAULT '{}',
            captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (social_post_id, metric_date)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_social_post_metrics_post_date
        ON social_post_metrics (social_post_id, metric_date DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS social_post_attribution_events (
            id TEXT PRIMARY KEY,
            social_post_id TEXT NOT NULL REFERENCES social_posts(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            event_source TEXT,
            event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            value INTEGER NOT NULL DEFAULT 1,
            metadata_json JSONB NOT NULL DEFAULT '{}'
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_social_post_attribution_post
        ON social_post_attribution_events (social_post_id, event_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_social_post_attribution_business
        ON social_post_attribution_events (business_id, event_type, event_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS social_post_attribution_events")
    op.execute("DROP TABLE IF EXISTS social_post_metrics")
    op.execute("DROP TABLE IF EXISTS social_posts")
