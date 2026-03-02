"""create prospecting leads table if missing

Revision ID: 20260302_003
Revises: 20260302_002
Create Date: 2026-03-02 18:55:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260302_003"
down_revision = "20260302_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prospectingleads (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            phone TEXT,
            website TEXT,
            email TEXT,
            telegram_url TEXT,
            whatsapp_url TEXT,
            messenger_links_json JSONB,
            rating DOUBLE PRECISION,
            reviews_count INTEGER,
            source_url TEXT,
            google_id TEXT,
            source TEXT DEFAULT 'apify_yandex',
            source_external_id TEXT,
            category TEXT,
            location JSONB,
            status TEXT NOT NULL DEFAULT 'new',
            selected_channel TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_prospectingleads_created_at ON prospectingleads(created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_prospectingleads_status ON prospectingleads(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_prospectingleads_source_external_id ON prospectingleads(source_external_id)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_source_external_id")
    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_status")
    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_created_at")
    op.execute("DROP TABLE IF EXISTS prospectingleads")
