"""fix finance schema compatibility (financialtransactions + roidata)

Revision ID: 20260224_003
Revises: 20260224_002
Create Date: 2026-02-24
"""

from alembic import op
from sqlalchemy import text


revision = "20260224_003"
down_revision = "20260224_002"
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
    if _has_table("financialtransactions"):
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS user_id TEXT")
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS business_id TEXT")
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS transaction_date DATE")
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS client_type TEXT DEFAULT 'new'")
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS services TEXT")
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS notes TEXT")
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS master_id TEXT")
        op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS roidata (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            investment_amount NUMERIC(12,2) DEFAULT 0,
            returns_amount NUMERIC(12,2) DEFAULT 0,
            roi_percentage NUMERIC(8,2) DEFAULT 0,
            period_start DATE,
            period_end DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_roidata_user_id ON roidata(user_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_roidata_user_id")
    op.execute("DROP TABLE IF EXISTS roidata")
