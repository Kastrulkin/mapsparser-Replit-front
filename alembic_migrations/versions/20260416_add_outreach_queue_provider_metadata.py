"""add provider metadata to outreachsendqueue

Revision ID: 20260416_001
Revises: 20260306_001
Create Date: 2026-04-16 15:05:00.000000
"""

from alembic import op


revision = "20260416_001"
down_revision = "20260321_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS provider_name TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS provider_account_id TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS recipient_kind TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS recipient_value TEXT
        """
    )


def downgrade():
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS recipient_value")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS recipient_kind")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS provider_account_id")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS provider_name")
