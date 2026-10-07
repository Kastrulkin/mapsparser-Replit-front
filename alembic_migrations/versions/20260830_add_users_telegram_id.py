"""add Telegram identity to users

Revision ID: 20260830_002
Revises: 20260830_001
Create Date: 2026-08-30
"""

from alembic import op


revision = "20260830_002"
down_revision = "20260830_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS telegram_id TEXT
        """
    )


def downgrade():
    # Telegram bindings may already be attached to accounts in installations
    # whose schema came from the legacy bootstrap. Keep identity data intact.
    pass
