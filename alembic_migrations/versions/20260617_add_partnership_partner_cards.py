"""add partnership partner cards pipeline

Revision ID: 20260617_001
Revises: 20260616_001
Create Date: 2026-06-17 12:00:00.000000
"""

from alembic import op


revision = "20260617_001"
down_revision = "20260616_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS partnership_partner_cards (
            id UUID PRIMARY KEY,
            business_id UUID NOT NULL,
            source_company_id TEXT,
            source_company_name TEXT NOT NULL,
            partner_name TEXT NOT NULL,
            partner_address TEXT,
            partner_city TEXT,
            partner_category TEXT,
            partner_kind TEXT NOT NULL DEFAULT 'business',
            yandex_maps_url TEXT,
            yandex_maps_match_status TEXT NOT NULL DEFAULT 'not_started',
            yandex_maps_match_confidence DOUBLE PRECISION,
            yandex_maps_candidates_json JSONB,
            parse_business_id UUID,
            audit_public_url TEXT,
            audit_slug TEXT,
            audit_status TEXT NOT NULL DEFAULT 'not_started',
            audit_generated_at TIMESTAMPTZ,
            audit_error TEXT,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            lead_sync_status TEXT NOT NULL DEFAULT 'not_synced',
            lead_sync_error TEXT,
            raw_payload_json JSONB,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_business_updated
        ON partnership_partner_cards (business_id, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_source_company
        ON partnership_partner_cards (business_id, source_company_name)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_match_status
        ON partnership_partner_cards (business_id, yandex_maps_match_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_partnership_partner_cards_lead_id
        ON partnership_partner_cards (lead_id)
        """
    )
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partner_source_company_id TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partner_source_company_name TEXT")
    op.execute("ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS partner_source_partner_id TEXT")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_partner_source
        ON prospectingleads (business_id, intent, partner_source_company_name)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_partner_source")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS partner_source_partner_id")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS partner_source_company_name")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS partner_source_company_id")
    op.execute("DROP INDEX IF EXISTS idx_partnership_partner_cards_lead_id")
    op.execute("DROP INDEX IF EXISTS idx_partnership_partner_cards_match_status")
    op.execute("DROP INDEX IF EXISTS idx_partnership_partner_cards_source_company")
    op.execute("DROP INDEX IF EXISTS idx_partnership_partner_cards_business_updated")
    op.execute("DROP TABLE IF EXISTS partnership_partner_cards")
