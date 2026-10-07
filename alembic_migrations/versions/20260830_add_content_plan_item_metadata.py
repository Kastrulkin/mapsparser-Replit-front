"""add canonical content plan item metadata

Revision ID: 20260830_001
Revises: 20260829_001
Create Date: 2026-08-30
"""

from alembic import op


revision = "20260830_001"
down_revision = "20260829_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE contentplanitems
        ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )


def downgrade():
    # The column may predate this migration because legacy content routes created
    # it at runtime. Retaining it avoids deleting existing publication metadata.
    pass
