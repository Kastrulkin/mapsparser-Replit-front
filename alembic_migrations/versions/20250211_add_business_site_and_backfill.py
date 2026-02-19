"""add business site column and backfill from website (canonical site, website kept for legacy)

Revision ID: 20250211_001
Revises: 20250210_001
Create Date: 2025-02-11

"""
from alembic import op

revision = "20250211_001"
down_revision = "20250210_001"
branch_labels = None
depends_on = None


def upgrade():
    # Каноническое поле сайта — site. website не удаляем (legacy/алиас).
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS site TEXT
        """
    )
    # Перенос данных: где site пустой, копируем из website
    op.execute(
        """
        UPDATE businesses
        SET site = website
        WHERE site IS NULL AND website IS NOT NULL AND website != ''
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE businesses
        DROP COLUMN IF EXISTS site
        """
    )
