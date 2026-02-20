"""add metrics counters columns and missing businesses fields

Revision ID: 20260220_001
Revises: 20250213_001
Create Date: 2026-02-20

"""
from alembic import op


revision = "20260220_001"
down_revision = "20250213_001"
branch_labels = None
depends_on = None


def upgrade():
    # externalbusinessstats counters used by runtime metrics aggregation
    op.execute(
        """
        ALTER TABLE externalbusinessstats
        ADD COLUMN IF NOT EXISTS photos_count INTEGER DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE externalbusinessstats
        ADD COLUMN IF NOT EXISTS news_count INTEGER DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE externalbusinessstats
        ADD COLUMN IF NOT EXISTS unanswered_reviews_count INTEGER DEFAULT 0
        """
    )

    # mapparseresults fallback counters (legacy table may be absent)
    op.execute(
        """
        ALTER TABLE IF EXISTS mapparseresults
        ADD COLUMN IF NOT EXISTS photos_count INTEGER DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS mapparseresults
        ADD COLUMN IF NOT EXISTS news_count INTEGER DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE IF EXISTS mapparseresults
        ADD COLUMN IF NOT EXISTS unanswered_reviews_count INTEGER DEFAULT 0
        """
    )

    # businesses fields used by progress/services flows
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS yandex_url TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS ai_agent_language TEXT
        """
    )

    # Normalize existing rows to non-null counters where possible
    op.execute(
        """
        UPDATE externalbusinessstats
        SET photos_count = COALESCE(photos_count, 0),
            news_count = COALESCE(news_count, 0),
            unanswered_reviews_count = COALESCE(unanswered_reviews_count, 0)
        """
    )
    # mapparseresults may be absent in some restored databases
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.mapparseresults') IS NOT NULL THEN
                UPDATE mapparseresults
                SET photos_count = COALESCE(photos_count, 0),
                    news_count = COALESCE(news_count, 0),
                    unanswered_reviews_count = COALESCE(unanswered_reviews_count, 0);
            END IF;
        END $$;
        """
    )


def downgrade():
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS ai_agent_language")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS yandex_url")
    op.execute("ALTER TABLE IF EXISTS mapparseresults DROP COLUMN IF EXISTS unanswered_reviews_count")
    op.execute("ALTER TABLE IF EXISTS mapparseresults DROP COLUMN IF EXISTS news_count")
    op.execute("ALTER TABLE IF EXISTS mapparseresults DROP COLUMN IF EXISTS photos_count")
    op.execute("ALTER TABLE externalbusinessstats DROP COLUMN IF EXISTS unanswered_reviews_count")
    op.execute("ALTER TABLE externalbusinessstats DROP COLUMN IF EXISTS news_count")
    op.execute("ALTER TABLE externalbusinessstats DROP COLUMN IF EXISTS photos_count")
