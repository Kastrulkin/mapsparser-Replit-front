"""extend crm integration request workflow

Revision ID: 20260810_001
Revises: 20260809_001
Create Date: 2026-08-10
"""

from alembic import op


revision = "20260810_001"
down_revision = "20260809_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE crm_integration_requests ADD COLUMN IF NOT EXISTS crm_url TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE crm_integration_requests ADD COLUMN IF NOT EXISTS contact TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE crm_integration_requests ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'business'")
    op.execute("ALTER TABLE crm_integration_requests ADD COLUMN IF NOT EXISTS scope_id TEXT")
    op.execute("ALTER TABLE crm_integration_requests DROP CONSTRAINT IF EXISTS chk_crm_integration_request_status")
    op.execute(
        """
        ALTER TABLE crm_integration_requests
        ADD CONSTRAINT chk_crm_integration_request_status
        CHECK (status IN ('open', 'reviewing', 'planned', 'connected', 'closed', 'declined'))
        """
    )
    op.execute("UPDATE crm_integration_requests SET scope_id = business_id WHERE scope_id IS NULL")
    op.execute("DROP INDEX IF EXISTS uq_crm_integration_requests_open_name")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_crm_integration_requests_open_name
        ON crm_integration_requests (business_id, crm_name_normalized)
        WHERE status IN ('open', 'reviewing', 'planned', 'connected')
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_crm_integration_requests_status ON crm_integration_requests (status, updated_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS growth_rhythm_reminder_deliveries (
            dedupe_key TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            telegram_id TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            period_key TEXT NOT NULL,
            reminder_kind TEXT NOT NULL,
            message_text TEXT NOT NULL,
            reply_markup_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_growth_rhythm_reminder_kind CHECK (reminder_kind IN ('before_due', 'overdue')),
            CONSTRAINT chk_growth_rhythm_reminder_scope CHECK (scope_type IN ('business', 'network'))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_growth_rhythm_reminder_pending ON growth_rhythm_reminder_deliveries (created_at) WHERE sent_at IS NULL"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth_rhythm_reminder_deliveries")
    op.execute("DROP INDEX IF EXISTS idx_crm_integration_requests_status")
    op.execute("DROP INDEX IF EXISTS uq_crm_integration_requests_open_name")
    op.execute("UPDATE crm_integration_requests SET status = 'closed' WHERE status = 'connected'")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_crm_integration_requests_open_name
        ON crm_integration_requests (business_id, crm_name_normalized)
        WHERE status IN ('open', 'reviewing', 'planned')
        """
    )
    op.execute("ALTER TABLE crm_integration_requests DROP CONSTRAINT IF EXISTS chk_crm_integration_request_status")
    op.execute(
        """
        ALTER TABLE crm_integration_requests
        ADD CONSTRAINT chk_crm_integration_request_status
        CHECK (status IN ('open', 'reviewing', 'planned', 'closed', 'declined'))
        """
    )
    op.execute("ALTER TABLE crm_integration_requests DROP COLUMN IF EXISTS scope_id")
    op.execute("ALTER TABLE crm_integration_requests DROP COLUMN IF EXISTS scope_type")
    op.execute("ALTER TABLE crm_integration_requests DROP COLUMN IF EXISTS contact")
    op.execute("ALTER TABLE crm_integration_requests DROP COLUMN IF EXISTS crm_url")
