"""move partnership lead columns out of request-time DDL

Revision ID: 20260830_003
Revises: 20260830_002
Create Date: 2026-08-30
"""

from alembic import op


revision = "20260830_003"
down_revision = "20260830_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE prospectingleads
            ADD COLUMN IF NOT EXISTS partnership_stage TEXT DEFAULT 'imported',
            ADD COLUMN IF NOT EXISTS pilot_cohort TEXT DEFAULT 'backlog',
            ADD COLUMN IF NOT EXISTS parse_business_id UUID,
            ADD COLUMN IF NOT EXISTS created_by UUID,
            ADD COLUMN IF NOT EXISTS source_kind TEXT,
            ADD COLUMN IF NOT EXISTS source_provider TEXT,
            ADD COLUMN IF NOT EXISTS external_place_id TEXT,
            ADD COLUMN IF NOT EXISTS external_source_id TEXT,
            ADD COLUMN IF NOT EXISTS dedupe_key TEXT,
            ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS lon DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS matched_sources_json JSONB,
            ADD COLUMN IF NOT EXISTS deferred_reason TEXT,
            ADD COLUMN IF NOT EXISTS deferred_until DATE,
            ADD COLUMN IF NOT EXISTS preferred_language TEXT,
            ADD COLUMN IF NOT EXISTS enabled_languages JSONB
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_stage
        ON prospectingleads (intent, partnership_stage)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_external_source
        ON prospectingleads (business_id, intent, external_source_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_intent_phone
        ON prospectingleads (business_id, intent, phone)
        """
    )


def downgrade():
    # These columns may contain lead history created before this migration.
    # Retaining them makes rollback non-destructive.
    pass
