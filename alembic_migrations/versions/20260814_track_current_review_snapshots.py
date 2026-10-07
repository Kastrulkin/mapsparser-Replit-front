"""Track reviews present in the latest complete provider snapshot.

Revision ID: 20260814_003
Revises: 20260814_002
"""

from alembic import op


revision = "20260814_003"
down_revision = "20260814_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE externalbusinessreviews
            ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP WITHOUT TIME ZONE,
            ADD COLUMN IF NOT EXISTS last_complete_snapshot_id UUID;

        UPDATE externalbusinessreviews
        SET last_seen_at = COALESCE(last_seen_at, updated_at, created_at)
        WHERE last_seen_at IS NULL;

        CREATE INDEX IF NOT EXISTS idx_external_reviews_business_current
            ON externalbusinessreviews (business_id, is_current, published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_external_reviews_snapshot
            ON externalbusinessreviews (last_complete_snapshot_id)
            WHERE last_complete_snapshot_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_external_reviews_snapshot;
        DROP INDEX IF EXISTS idx_external_reviews_business_current;
        ALTER TABLE externalbusinessreviews
            DROP COLUMN IF EXISTS last_complete_snapshot_id,
            DROP COLUMN IF EXISTS last_seen_at,
            DROP COLUMN IF EXISTS is_current;
        """
    )
