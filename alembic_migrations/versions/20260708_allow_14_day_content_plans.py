"""allow 14 day content plans

Revision ID: 20260708_001
Revises: 20260706_001
Create Date: 2026-07-08
"""

from alembic import op


revision = "20260708_001"
down_revision = "20260706_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE contentplans DROP CONSTRAINT IF EXISTS chk_contentplans_period_days")
    op.execute(
        """
        ALTER TABLE contentplans
        ADD CONSTRAINT chk_contentplans_period_days
        CHECK (period_days IN (14, 30, 60, 90))
        """
    )


def downgrade():
    op.execute("ALTER TABLE contentplans DROP CONSTRAINT IF EXISTS chk_contentplans_period_days")
    op.execute(
        """
        ALTER TABLE contentplans
        ADD CONSTRAINT chk_contentplans_period_days
        CHECK (period_days IN (30, 60, 90))
        """
    )
