"""add business subscription end date

Revision ID: 20260616_001
Revises: 20260609_005
Create Date: 2026-06-16
"""

from alembic import op


revision = "20260616_001"
down_revision = "20260609_005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS subscription_ends_at TIMESTAMP
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE businesses
        DROP COLUMN IF EXISTS subscription_ends_at
        """
    )
