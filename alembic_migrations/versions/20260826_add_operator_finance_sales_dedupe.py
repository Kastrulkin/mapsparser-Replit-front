"""add provenance and dedupe keys for Operator sales imports

Revision ID: 20260826_002
Revises: 20260826_001
Create Date: 2026-08-26
"""

from alembic import op


revision = "20260826_002"
down_revision = "20260826_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS source TEXT")
    op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS import_batch_id TEXT")
    op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS source_hash TEXT")
    op.execute("ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS duplicate_key TEXT")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_financialtransactions_business_duplicate_key "
        "ON financialtransactions(business_id, duplicate_key) WHERE duplicate_key IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_financialtransactions_import_batch "
        "ON financialtransactions(business_id, import_batch_id) WHERE import_batch_id IS NOT NULL"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_financialtransactions_import_batch")
    op.execute("DROP INDEX IF EXISTS uq_financialtransactions_business_duplicate_key")
    op.execute("ALTER TABLE financialtransactions DROP COLUMN IF EXISTS duplicate_key")
    op.execute("ALTER TABLE financialtransactions DROP COLUMN IF EXISTS source_hash")
    op.execute("ALTER TABLE financialtransactions DROP COLUMN IF EXISTS import_batch_id")
    op.execute("ALTER TABLE financialtransactions DROP COLUMN IF EXISTS source")
