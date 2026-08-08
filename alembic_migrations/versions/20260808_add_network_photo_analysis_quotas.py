"""add network photo analysis quotas

Revision ID: 20260808_001
Revises: 20260805_003
Create Date: 2026-08-08
"""

from alembic import op


revision = "20260808_001"
down_revision = "20260805_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS network_photo_analysis_quotas (
            network_id TEXT PRIMARY KEY REFERENCES networks(id) ON DELETE CASCADE,
            granted_analyses INTEGER NOT NULL DEFAULT 0,
            consumed_analyses INTEGER NOT NULL DEFAULT 0,
            reserved_analyses INTEGER NOT NULL DEFAULT 0,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_network_photo_quota_counts CHECK (
                granted_analyses >= 0
                AND consumed_analyses >= 0
                AND reserved_analyses >= 0
                AND consumed_analyses + reserved_analyses <= granted_analyses
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS network_photo_analysis_quota_reservations (
            id TEXT PRIMARY KEY,
            network_id TEXT NOT NULL REFERENCES network_photo_analysis_quotas(network_id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            asset_id TEXT NOT NULL REFERENCES photo_assets(id) ON DELETE CASCADE,
            asset_version INTEGER NOT NULL DEFAULT 1,
            idempotency_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'reserved',
            consumed_at TIMESTAMPTZ,
            released_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_network_photo_quota_reservation UNIQUE (network_id, idempotency_key),
            CONSTRAINT chk_network_photo_quota_reservation_status CHECK (
                status IN ('reserved', 'consumed', 'released')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_network_photo_quota_reservations_status
        ON network_photo_analysis_quota_reservations (network_id, status, updated_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS network_photo_analysis_quota_reservations")
    op.execute("DROP TABLE IF EXISTS network_photo_analysis_quotas")
