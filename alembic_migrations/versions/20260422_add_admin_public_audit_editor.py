"""add admin public audit editor fields

Revision ID: 20260422_001
Revises: 20260421_002
Create Date: 2026-04-22 17:15:00.000000
"""

from alembic import op


revision = "20260422_001"
down_revision = "20260421_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS business_id UUID")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS business_profile TEXT")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'admin_prospecting_public_audit'")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS generated_json JSONB")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edited_json JSONB")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS published_json JSONB")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edit_status TEXT NOT NULL DEFAULT 'generated'")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edited_by UUID")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS published_by UUID")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ")

    op.execute(
        """
        UPDATE adminprospectingleadpublicoffers
        SET generated_json = COALESCE(generated_json, page_json),
            published_json = COALESCE(published_json, page_json),
            business_profile = COALESCE(NULLIF(business_profile, ''), NULLIF(page_json->'audit'->>'audit_profile', '')),
            edit_status = CASE
                WHEN edited_json IS NOT NULL AND published_json IS NOT NULL THEN 'published'
                WHEN edited_json IS NOT NULL THEN 'draft_edited'
                ELSE COALESCE(NULLIF(edit_status, ''), 'generated')
            END
        WHERE generated_json IS NULL
           OR published_json IS NULL
           OR COALESCE(edit_status, '') = ''
           OR COALESCE(business_profile, '') = ''
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_adminprospectingleadpublicoffers_edit_status
        ON adminprospectingleadpublicoffers (edit_status, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_adminprospectingleadpublicoffers_business_id
        ON adminprospectingleadpublicoffers (business_id)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_adminprospectingleadpublicoffers_business_id")
    op.execute("DROP INDEX IF EXISTS idx_adminprospectingleadpublicoffers_edit_status")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS published_at")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS published_by")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS edited_at")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS edited_by")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS edit_status")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS published_json")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS edited_json")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS generated_json")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS source_type")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS business_profile")
    op.execute("ALTER TABLE adminprospectingleadpublicoffers DROP COLUMN IF EXISTS business_id")
