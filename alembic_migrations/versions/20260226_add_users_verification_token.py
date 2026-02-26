"""add verification_token column to users

Revision ID: 20260226_002
Revises: 20260226_001
Create Date: 2026-02-26
"""

from alembic import op
from sqlalchemy import text


revision = "20260226_002"
down_revision = "20260226_001"
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
        ADD COLUMN IF NOT EXISTS verification_token TEXT
        """
    )


def downgrade():
    if not _has_table("users"):
        return

    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS verification_token")

