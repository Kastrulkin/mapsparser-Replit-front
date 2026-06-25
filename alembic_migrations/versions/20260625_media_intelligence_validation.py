"""add media intelligence validation state

Revision ID: 20260625_002
Revises: 20260625_001
Create Date: 2026-06-25 16:30:00.000000
"""

from alembic import op


revision = "20260625_002"
down_revision = "20260625_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE photo_assets ADD COLUMN IF NOT EXISTS analysis_status TEXT NOT NULL DEFAULT 'not_analyzed'")
    op.execute("ALTER TABLE photo_assets ADD COLUMN IF NOT EXISTS analysis_error TEXT")
    op.execute("ALTER TABLE photo_assets ADD COLUMN IF NOT EXISTS analysis_attempts INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE photo_assets ADD COLUMN IF NOT EXISTS last_analyzed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE photo_assets ADD COLUMN IF NOT EXISTS content_hash TEXT")
    op.execute("ALTER TABLE photo_assets ADD COLUMN IF NOT EXISTS meta_storage_key TEXT")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_photo_assets_business_analysis_status
        ON photo_assets (business_id, analysis_status, updated_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_photo_assets_business_analysis_status")
    op.execute("ALTER TABLE photo_assets DROP COLUMN IF EXISTS meta_storage_key")
    op.execute("ALTER TABLE photo_assets DROP COLUMN IF EXISTS content_hash")
    op.execute("ALTER TABLE photo_assets DROP COLUMN IF EXISTS last_analyzed_at")
    op.execute("ALTER TABLE photo_assets DROP COLUMN IF EXISTS analysis_attempts")
    op.execute("ALTER TABLE photo_assets DROP COLUMN IF EXISTS analysis_error")
    op.execute("ALTER TABLE photo_assets DROP COLUMN IF EXISTS analysis_status")
