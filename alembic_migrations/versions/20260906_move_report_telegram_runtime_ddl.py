"""Move public-report and Telegram history schema into Alembic.

Revision ID: 20260906_010
Revises: 20260906_009

Exact parity with the active bootstrap callers; their existing rows survive.
UserNews already belongs to earlier Alembic revisions (including 20260906_003).
"""
from alembic import op

revision = "20260906_010"
down_revision = "20260906_009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS callback_recovery_history (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            triggered_by TEXT NOT NULL,
            send_telegram_report BOOLEAN NOT NULL DEFAULT FALSE,
            include_retry BOOLEAN NOT NULL DEFAULT TRUE,
            replayed_count INTEGER NOT NULL DEFAULT 0,
            sent_count INTEGER NOT NULL DEFAULT 0,
            retried_count INTEGER NOT NULL DEFAULT 0,
            dlq_count INTEGER NOT NULL DEFAULT 0,
            telegram_sent_count INTEGER NOT NULL DEFAULT 0,
            action_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            report_text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_callback_recovery_history_tenant_created
        ON callback_recovery_history (tenant_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS support_export_send_history (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            triggered_by TEXT NOT NULL,
            action_id TEXT NULL,
            telegram_sent_count INTEGER NOT NULL DEFAULT 0,
            target_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            report_text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_support_export_send_history_tenant_created
        ON support_export_send_history (tenant_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publicreportrequests (
            slug TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'apify_yandex',
            status TEXT NOT NULL DEFAULT 'queued',
            page_json JSONB NOT NULL,
            result_json JSONB,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade():
    # Preserve customer requests and operational history during code rollback.
    pass
