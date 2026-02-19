"""add partial unique index for latest cards per business

Revision ID: 20250212_001
Revises: 20250211_002
Create Date: 2025-02-12

"""
from alembic import op


revision = "20250212_001"
down_revision = "20250211_002"
branch_labels = None
depends_on = None


def upgrade():
    # Гарантия: не более одной is_latest = TRUE записи на бизнес.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_cards_latest_per_business
        ON cards (business_id)
        WHERE is_latest IS TRUE
        """
    )


def downgrade():
    op.execute(
        "DROP INDEX IF EXISTS uq_cards_latest_per_business"
    )

