"""add evidence-backed creator taxonomy

Revision ID: 20260825_001
Revises: 20260824_002
Create Date: 2026-08-25 10:30:00.000000
"""

from alembic import op


revision = "20260825_001"
down_revision = "20260824_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_profile_taxonomy (
            creator_profile_id UUID PRIMARY KEY REFERENCES creator_profiles(id) ON DELETE CASCADE,
            primary_topic TEXT,
            secondary_topics_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            content_styles_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            observed_formats_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            confirmed_formats_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            home_city TEXT,
            home_district TEXT,
            metro_stations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            discovery_geography_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            content_geographies_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            audience_geography_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            audience_types_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            audience_size_band TEXT NOT NULL DEFAULT 'unknown',
            segment_fit_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            confidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            classification_status TEXT NOT NULL DEFAULT 'needs_review',
            classification_version TEXT NOT NULL,
            classified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reviewed_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_taxonomy_status CHECK (
                classification_status IN ('automated', 'needs_review', 'reviewed', 'rejected')
            ),
            CONSTRAINT ck_creator_taxonomy_audience_band CHECK (
                audience_size_band IN ('nano', 'micro', 'mid', 'macro', 'unknown')
            )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_taxonomy_city ON creator_profile_taxonomy(LOWER(home_city))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_taxonomy_district ON creator_profile_taxonomy(LOWER(home_district))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_taxonomy_topics ON creator_profile_taxonomy USING GIN(secondary_topics_json)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_taxonomy_styles ON creator_profile_taxonomy USING GIN(content_styles_json)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_taxonomy_content_geo ON creator_profile_taxonomy USING GIN(content_geographies_json)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_taxonomy_audience_types ON creator_profile_taxonomy USING GIN(audience_types_json)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_taxonomy_segment_fit ON creator_profile_taxonomy USING GIN(segment_fit_json)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS creator_profile_taxonomy")
