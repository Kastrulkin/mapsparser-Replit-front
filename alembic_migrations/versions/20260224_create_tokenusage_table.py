"""create tokenusage table if missing

Revision ID: 20260224_004
Revises: 20260224_003
Create Date: 2026-02-24
"""

from alembic import op
from sqlalchemy import text


revision = "20260224_004"
down_revision = "20260224_003"
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
    if not _has_table("tokenusage"):
        op.execute(
            """
            CREATE TABLE tokenusage (
                id TEXT PRIMARY KEY,
                business_id TEXT,
                user_id TEXT,
                task_type TEXT,
                model TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                endpoint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    op.execute("CREATE INDEX IF NOT EXISTS idx_tokenusage_user_created ON tokenusage(user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tokenusage_business_created ON tokenusage(business_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tokenusage_task_created ON tokenusage(task_type, created_at)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_tokenusage_task_created")
    op.execute("DROP INDEX IF EXISTS idx_tokenusage_business_created")
    op.execute("DROP INDEX IF EXISTS idx_tokenusage_user_created")
    op.execute("DROP TABLE IF EXISTS tokenusage")
