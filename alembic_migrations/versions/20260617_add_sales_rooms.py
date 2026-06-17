"""add digital sales rooms

Revision ID: 20260617_002
Revises: 20260617_001
Create Date: 2026-06-17 16:30:00.000000
"""

from alembic import op


revision = "20260617_002"
down_revision = "20260617_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_rooms (
            id UUID PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            business_id UUID NOT NULL,
            mode TEXT NOT NULL,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            partner_card_id UUID REFERENCES partnership_partner_cards(id) ON DELETE SET NULL,
            data_mode TEXT NOT NULL DEFAULT 'template',
            audit_public_url TEXT,
            match_json JSONB,
            proposal_json JSONB,
            room_json JSONB NOT NULL,
            invitation_draft_id TEXT REFERENCES outreachmessagedrafts(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_rooms_business_updated
        ON sales_rooms (business_id, updated_at DESC)
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_rooms_lead ON sales_rooms (lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_rooms_partner_card ON sales_rooms (partner_card_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_events (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            metadata_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_events_room_created
        ON sales_room_events (room_id, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_sales_room_events_room_created")
    op.execute("DROP TABLE IF EXISTS sales_room_events")
    op.execute("DROP INDEX IF EXISTS idx_sales_rooms_partner_card")
    op.execute("DROP INDEX IF EXISTS idx_sales_rooms_lead")
    op.execute("DROP INDEX IF EXISTS idx_sales_rooms_business_updated")
    op.execute("DROP TABLE IF EXISTS sales_rooms")
