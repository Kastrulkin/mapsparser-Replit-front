"""add outreach search jobs table for async prospecting

Revision ID: 20260302_001
Revises: 20260226_002
Create Date: 2026-03-02
"""

from alembic import op
from sqlalchemy import text


revision = "20260302_001"
down_revision = "20260226_002"
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
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreachsearchjobs (
            id UUID PRIMARY KEY,
            source TEXT NOT NULL DEFAULT 'apify_yandex',
            actor_id TEXT,
            query TEXT NOT NULL,
            location TEXT NOT NULL,
            search_limit INTEGER NOT NULL DEFAULT 50,
            status TEXT NOT NULL DEFAULT 'queued',
            result_count INTEGER NOT NULL DEFAULT 0,
            created_by UUID,
            error_text TEXT,
            results_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachsearchjobs_created_at ON outreachsearchjobs(created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachsearchjobs_status ON outreachsearchjobs(status)"
    )

    if _has_table("prospectingleads"):
        op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'apify_yandex'")
        op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS source_external_id TEXT")
        op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS email TEXT")
        op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS telegram_url TEXT")
        op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS whatsapp_url TEXT")
        op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS messenger_links_json JSONB")
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_prospectingleads_source_external_id ON prospectingleads(source_external_id)"
        )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreachsearchjobs_created_at")
    op.execute("DROP INDEX IF EXISTS idx_outreachsearchjobs_status")
    op.execute("DROP TABLE IF EXISTS outreachsearchjobs")
    if _has_table("prospectingleads"):
        op.execute("DROP INDEX IF EXISTS idx_prospectingleads_source_external_id")
        op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS messenger_links_json")
        op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS whatsapp_url")
        op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS telegram_url")
        op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS email")
        op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS source_external_id")
        op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS source")
