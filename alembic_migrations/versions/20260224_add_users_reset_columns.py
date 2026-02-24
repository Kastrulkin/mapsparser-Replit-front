"""add reset password columns to users

Revision ID: 20260224_001
Revises: 20260220_001
Create Date: 2026-02-24
"""

from alembic import op
from sqlalchemy import text


revision = "20260224_001"
down_revision = "20260220_001"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            text("SELECT to_regclass(:tbl) IS NOT NULL"),
            {"tbl": f"public.{table_name.lower()}"},
        ).scalar()
    )


def upgrade():
    if not _has_table("users"):
        return

    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS reset_token TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP
        """
    )


def downgrade():
    if not _has_table("users"):
        return

    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS reset_token_expires")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS reset_token")
