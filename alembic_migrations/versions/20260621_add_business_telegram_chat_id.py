"""add telegram chat id for social publishing

Revision ID: 20260621_001
Revises: 20260619_001
Create Date: 2026-06-21 19:30:00.000000
"""

from alembic import op


revision = "20260621_001"
down_revision = "20260619_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT")


def downgrade():
    # Keep configured channel targets on downgrade; this migration is additive.
    pass
