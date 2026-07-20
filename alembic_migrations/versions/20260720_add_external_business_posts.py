"""add external business posts storage

Revision ID: 20260720_001
Revises: 20260718_001
Create Date: 2026-07-20 14:30:00.000000
"""

from alembic import op


revision = "20260720_001"
down_revision = "20260718_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS externalbusinessposts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            account_id TEXT,
            source TEXT NOT NULL,
            external_post_id TEXT,
            title TEXT,
            text TEXT,
            published_at TIMESTAMP,
            image_url TEXT,
            raw_payload TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_externalbusinessposts_business_published
        ON externalbusinessposts(business_id, published_at DESC, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_externalbusinessposts_source
        ON externalbusinessposts(source)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_externalbusinessposts_source")
    op.execute("DROP INDEX IF EXISTS idx_externalbusinessposts_business_published")
    op.execute("DROP TABLE IF EXISTS externalbusinessposts")
