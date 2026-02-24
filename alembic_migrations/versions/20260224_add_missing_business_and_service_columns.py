"""add missing businesses/userservices columns for compatibility

Revision ID: 20260224_002
Revises: 20260224_001
Create Date: 2026-02-24
"""

from alembic import op
from sqlalchemy import text


revision = "20260224_002"
down_revision = "20260224_001"
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
    if _has_table("businesses"):
        op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS yandex_url TEXT")
        op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS country TEXT")

    if _has_table("userservices"):
        op.execute("ALTER TABLE userservices ADD COLUMN IF NOT EXISTS optimized_name TEXT")
        op.execute("ALTER TABLE userservices ADD COLUMN IF NOT EXISTS optimized_description TEXT")


def downgrade():
    if _has_table("userservices"):
        op.execute("ALTER TABLE userservices DROP COLUMN IF EXISTS optimized_description")
        op.execute("ALTER TABLE userservices DROP COLUMN IF EXISTS optimized_name")

    if _has_table("businesses"):
        op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS country")
        op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS yandex_url")

