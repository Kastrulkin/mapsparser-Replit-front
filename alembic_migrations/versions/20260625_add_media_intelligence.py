"""add media intelligence runtime tables

Revision ID: 20260625_001
Revises: 20260621_001
Create Date: 2026-06-25 15:00:00.000000
"""

from alembic import op


revision = "20260625_001"
down_revision = "20260621_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_capability_settings (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            capability TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            enabled_by TEXT,
            enabled_at TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (business_id, capability)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_capability_settings_business
        ON ai_capability_settings (business_id, capability)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage_events (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            action_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            raw_units NUMERIC NOT NULL DEFAULT 0,
            raw_unit_type TEXT NOT NULL,
            provider_cost NUMERIC,
            estimated_credits INTEGER NOT NULL DEFAULT 0,
            charged_credits INTEGER NOT NULL DEFAULT 0,
            reservation_id TEXT,
            cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_usage_events_business_action
        ON ai_usage_events (business_id, action_type, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS photo_assets (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            source TEXT NOT NULL DEFAULT 'manual',
            original_url TEXT,
            storage_key TEXT,
            versions_json JSONB NOT NULL DEFAULT '{}',
            metadata_json JSONB NOT NULL DEFAULT '{}',
            category TEXT,
            quality_score INTEGER NOT NULL DEFAULT 0,
            freshness_score INTEGER NOT NULL DEFAULT 0,
            orientation TEXT,
            people_count INTEGER NOT NULL DEFAULT 0,
            service_tags JSONB NOT NULL DEFAULT '[]',
            suitable_platforms JSONB NOT NULL DEFAULT '[]',
            asset_version INTEGER NOT NULL DEFAULT 1,
            last_used_at TIMESTAMPTZ,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_photo_assets_business_category
        ON photo_assets (business_id, category, quality_score DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_runtime_cache (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            action_type TEXT NOT NULL,
            asset_id TEXT REFERENCES photo_assets(id) ON DELETE CASCADE,
            asset_version INTEGER NOT NULL DEFAULT 1,
            prompt_hash TEXT NOT NULL,
            context_hash TEXT NOT NULL,
            result_json JSONB NOT NULL DEFAULT '{}',
            usage_event_id TEXT REFERENCES ai_usage_events(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (provider, action_type, asset_id, asset_version, prompt_hash, context_hash)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_runtime_cache_asset
        ON ai_runtime_cache (asset_id, action_type, updated_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS photo_asset_usage_events (
            id TEXT PRIMARY KEY,
            photo_asset_id TEXT NOT NULL REFERENCES photo_assets(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            usage_type TEXT NOT NULL,
            target_id TEXT,
            target_platform TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_photo_asset_usage_asset
        ON photo_asset_usage_events (photo_asset_id, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS photo_asset_usage_events")
    op.execute("DROP TABLE IF EXISTS ai_runtime_cache")
    op.execute("DROP TABLE IF EXISTS photo_assets")
    op.execute("DROP TABLE IF EXISTS ai_usage_events")
    op.execute("DROP TABLE IF EXISTS ai_capability_settings")
