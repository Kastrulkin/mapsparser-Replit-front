"""add rich payload columns to prospecting leads

Revision ID: 20260321_001
Revises: 20260311_001
Create Date: 2026-03-21 13:10:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260321_001"
down_revision = "20260311_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS logo_url TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS photos_json JSONB")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS services_json JSONB")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS reviews_json JSONB")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS raw_payload_json JSONB")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS search_payload_json JSONB")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS enrich_payload_json JSONB")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_prospectingleads_source_external_id ON prospectingleads(source_external_id)"
    )


def downgrade():
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS enrich_payload_json")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS search_payload_json")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS raw_payload_json")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS reviews_json")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS services_json")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS photos_json")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS description")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS logo_url")
