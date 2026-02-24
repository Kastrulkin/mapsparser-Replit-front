"""add metrics counters columns for external stats and map parse results

Revision ID: 20260220_001
Revises: 20250213_001
Create Date: 2026-02-20
"""
from alembic import op
from sqlalchemy import text

revision = "20260220_001"
down_revision = "20250213_001"
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
    if _has_table("externalbusinessstats"):
        op.execute("ALTER TABLE externalbusinessstats ADD COLUMN IF NOT EXISTS photos_count INTEGER DEFAULT 0")
        op.execute("ALTER TABLE externalbusinessstats ADD COLUMN IF NOT EXISTS news_count INTEGER DEFAULT 0")
        op.execute("ALTER TABLE externalbusinessstats ADD COLUMN IF NOT EXISTS unanswered_reviews_count INTEGER DEFAULT 0")
        op.execute(
            """
            UPDATE externalbusinessstats
            SET photos_count = COALESCE(photos_count, 0),
                news_count = COALESCE(news_count, 0),
                unanswered_reviews_count = COALESCE(unanswered_reviews_count, 0)
            """
        )

    if _has_table("mapparseresults"):
        op.execute("ALTER TABLE mapparseresults ADD COLUMN IF NOT EXISTS photos_count INTEGER DEFAULT 0")
        op.execute("ALTER TABLE mapparseresults ADD COLUMN IF NOT EXISTS news_count INTEGER DEFAULT 0")
        op.execute("ALTER TABLE mapparseresults ADD COLUMN IF NOT EXISTS unanswered_reviews_count INTEGER DEFAULT 0")
        op.execute(
            """
            UPDATE mapparseresults
            SET photos_count = COALESCE(photos_count, 0),
                news_count = COALESCE(news_count, 0),
                unanswered_reviews_count = COALESCE(unanswered_reviews_count, 0)
            """
        )


def downgrade():
    if _has_table("mapparseresults"):
        op.execute("ALTER TABLE mapparseresults DROP COLUMN IF EXISTS unanswered_reviews_count")
        op.execute("ALTER TABLE mapparseresults DROP COLUMN IF EXISTS news_count")
        op.execute("ALTER TABLE mapparseresults DROP COLUMN IF EXISTS photos_count")
    if _has_table("externalbusinessstats"):
        op.execute("ALTER TABLE externalbusinessstats DROP COLUMN IF EXISTS unanswered_reviews_count")
        op.execute("ALTER TABLE externalbusinessstats DROP COLUMN IF EXISTS news_count")
        op.execute("ALTER TABLE externalbusinessstats DROP COLUMN IF EXISTS photos_count")
