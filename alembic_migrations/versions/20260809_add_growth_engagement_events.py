"""add growth engagement requests and product analytics events

Revision ID: 20260809_001
Revises: 20260808_001
Create Date: 2026-08-09
"""

from alembic import op


revision = "20260809_001"
down_revision = "20260808_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_integration_requests (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            requested_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            crm_name TEXT NOT NULL,
            crm_name_normalized TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_crm_integration_request_status
                CHECK (status IN ('open', 'reviewing', 'planned', 'closed', 'declined'))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_crm_integration_requests_open_name
        ON crm_integration_requests (business_id, crm_name_normalized)
        WHERE status IN ('open', 'reviewing', 'planned')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_crm_integration_requests_business
        ON crm_integration_requests (business_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_analytics_events (
            id TEXT PRIMARY KEY,
            event_name TEXT NOT NULL,
            channel TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL,
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            scope_type TEXT,
            scope_id TEXT,
            screen TEXT NOT NULL DEFAULT '',
            target TEXT NOT NULL DEFAULT '',
            properties_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_product_analytics_channel CHECK (channel IN ('web', 'telegram_mini_app'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_product_analytics_events_business_time
        ON product_analytics_events (business_id, occurred_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_product_analytics_events_name_time
        ON product_analytics_events (event_name, occurred_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS product_analytics_events")
    op.execute("DROP TABLE IF EXISTS crm_integration_requests")
