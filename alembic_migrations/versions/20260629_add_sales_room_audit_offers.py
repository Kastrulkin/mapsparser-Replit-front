"""add sales room audit offers

Revision ID: 20260629_001
Revises: 20260625_002
Create Date: 2026-06-29
"""

from alembic import op


revision = "20260629_001"
down_revision = "20260625_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_participants (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            name TEXT,
            company TEXT,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            personal_data_consent_at TIMESTAMPTZ,
            personal_data_consent_version TEXT,
            privacy_accepted_at TIMESTAMPTZ,
            consent_ip TEXT,
            consent_user_agent TEXT,
            verification_token TEXT,
            access_token TEXT NOT NULL,
            verified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (room_id, email)
        )
        """
    )
    op.execute("ALTER TABLE sales_room_participants ADD COLUMN IF NOT EXISTS personal_data_consent_at TIMESTAMPTZ")
    op.execute("ALTER TABLE sales_room_participants ADD COLUMN IF NOT EXISTS personal_data_consent_version TEXT")
    op.execute("ALTER TABLE sales_room_participants ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMPTZ")
    op.execute("ALTER TABLE sales_room_participants ADD COLUMN IF NOT EXISTS consent_ip TEXT")
    op.execute("ALTER TABLE sales_room_participants ADD COLUMN IF NOT EXISTS consent_user_agent TEXT")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_participants_verification_token
        ON sales_room_participants (verification_token)
        WHERE verification_token IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_room_participants_access_token
        ON sales_room_participants (access_token)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_audit_offers (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            lead_email TEXT,
            company_name TEXT NOT NULL,
            company_map_url TEXT NOT NULL,
            company_address TEXT,
            platform TEXT NOT NULL DEFAULT 'yandex',
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            admin_comment TEXT,
            offer_title TEXT,
            offer_text TEXT,
            button_text TEXT,
            prepared_audit_slug TEXT,
            prepared_audit_url TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            requested_by_participant_id UUID REFERENCES sales_room_participants(id) ON DELETE SET NULL,
            requested_user_id UUID,
            requested_at TIMESTAMPTZ,
            processing_started_at TIMESTAMPTZ,
            ready_at TIMESTAMPTZ,
            opened_at TIMESTAMPTZ,
            email_sent_at TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (room_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sales_room_audit_offers_processing
        ON sales_room_audit_offers (status, processing_started_at)
        WHERE status = 'processing'
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_sales_room_audit_offers_processing")
    op.execute("DROP TABLE IF EXISTS sales_room_audit_offers")
    op.execute("DROP INDEX IF EXISTS idx_sales_room_participants_access_token")
    op.execute("DROP INDEX IF EXISTS idx_sales_room_participants_verification_token")
    op.execute("DROP TABLE IF EXISTS sales_room_participants")
