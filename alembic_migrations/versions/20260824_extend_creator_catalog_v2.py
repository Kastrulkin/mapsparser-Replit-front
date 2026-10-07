"""extend creator catalog platforms and verification lifecycle

Revision ID: 20260824_002
Revises: 20260824_001
Create Date: 2026-08-24 18:30:00.000000
"""

from alembic import op


revision = "20260824_002"
down_revision = "20260824_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE creator_channels DROP CONSTRAINT IF EXISTS ck_creator_channels_platform")
    op.execute(
        """
        ALTER TABLE creator_channels
        ADD CONSTRAINT ck_creator_channels_platform CHECK (
            platform IN ('telegram', 'vk', 'website', 'instagram', 'threads', 'tiktok', 'youtube', 'other')
        )
        """
    )
    op.execute("ALTER TABLE creator_channels ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'pending'")
    op.execute("ALTER TABLE creator_channels ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ")
    op.execute("ALTER TABLE creator_channels ADD COLUMN IF NOT EXISTS next_check_at TIMESTAMPTZ")
    op.execute("ALTER TABLE creator_channels ADD COLUMN IF NOT EXISTS verification_note TEXT")
    op.execute("ALTER TABLE creator_channels DROP CONSTRAINT IF EXISTS ck_creator_channels_verification")
    op.execute(
        """
        ALTER TABLE creator_channels
        ADD CONSTRAINT ck_creator_channels_verification CHECK (
            verification_status IN ('pending', 'verified', 'stale', 'mismatch', 'inaccessible', 'excluded')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_creator_channels_recheck
        ON creator_channels(verification_status, next_check_at)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_creator_channels_recheck")
    op.execute("ALTER TABLE creator_channels DROP CONSTRAINT IF EXISTS ck_creator_channels_verification")
    op.execute("ALTER TABLE creator_channels DROP COLUMN IF EXISTS verification_note")
    op.execute("ALTER TABLE creator_channels DROP COLUMN IF EXISTS next_check_at")
    op.execute("ALTER TABLE creator_channels DROP COLUMN IF EXISTS verified_at")
    op.execute("ALTER TABLE creator_channels DROP COLUMN IF EXISTS verification_status")
    op.execute("ALTER TABLE creator_channels DROP CONSTRAINT IF EXISTS ck_creator_channels_platform")
    op.execute(
        """
        ALTER TABLE creator_channels
        ADD CONSTRAINT ck_creator_channels_platform CHECK (
            platform IN ('telegram', 'vk', 'website', 'instagram', 'tiktok', 'youtube', 'other')
        )
        """
    )
