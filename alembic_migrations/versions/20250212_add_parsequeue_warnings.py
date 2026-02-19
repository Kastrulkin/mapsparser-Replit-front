"""add warnings column to parsequeue

Revision ID: 20250212_002
Revises: 20250212_001
Create Date: 2025-02-12
"""

from alembic import op


revision = "20250212_002"
down_revision = "20250212_001"
branch_labels = None
depends_on = None


def upgrade():
    # warnings: текстовое поле под machine-readable предупреждения
    op.execute(
        """
        ALTER TABLE parsequeue
        ADD COLUMN IF NOT EXISTS warnings TEXT
        """
    )


def downgrade():
    # Откатываем только то, что добавили в этой ревизии
    op.execute(
        """
        ALTER TABLE parsequeue
        DROP COLUMN IF EXISTS warnings
        """
    )

