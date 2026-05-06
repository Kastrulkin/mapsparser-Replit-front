"""add seo views to content plan items

Revision ID: 20260505_001
Revises: 20260430_001
Create Date: 2026-05-05 10:55:00.000000
"""

from alembic import op


revision = "20260505_001"
down_revision = "20260430_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE contentplanitems ADD COLUMN IF NOT EXISTS seo_views INTEGER NOT NULL DEFAULT 0")


def downgrade():
    op.execute("ALTER TABLE contentplanitems DROP COLUMN IF EXISTS seo_views")
