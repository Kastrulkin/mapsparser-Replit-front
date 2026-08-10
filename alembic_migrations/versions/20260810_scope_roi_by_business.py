"""scope ROI records by business

Revision ID: 20260810_002_roi
Revises: 20260810_001
Create Date: 2026-08-10
"""

from alembic import op


revision = "20260810_002_roi"
down_revision = "20260810_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE roidata ADD COLUMN IF NOT EXISTS business_id TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_roidata_business_created "
        "ON roidata(business_id, created_at DESC)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_roidata_business_created")
    op.execute("ALTER TABLE roidata DROP COLUMN IF EXISTS business_id")
