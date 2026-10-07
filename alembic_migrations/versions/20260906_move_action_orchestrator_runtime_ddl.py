"""Move ActionOrchestrator runtime schema setup into Alembic.

Revision ID: 20260906_005
Revises: 20260906_004
"""

from alembic import op


revision = "20260906_005"
down_revision = "20260906_004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS action_requests (
            action_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            capability TEXT NOT NULL,
            actor_json JSONB NOT NULL,
            payload_json JSONB NOT NULL,
            approval_json JSONB,
            billing_json JSONB,
            trace_id TEXT,
            idempotency_key TEXT NOT NULL,
            status TEXT NOT NULL,
            result_json JSONB,
            error_code TEXT,
            error_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_action_requests_tenant_idempotency ON action_requests(tenant_id, idempotency_key)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_requests_status ON action_requests(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_requests_tenant_created ON action_requests(tenant_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS action_transitions (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            reason TEXT,
            meta_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_transitions_action_id ON action_transitions(action_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS action_approvals (
            action_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            requested_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            decider_actor_json JSONB,
            decision_reason TEXT,
            callback_url TEXT,
            resolved_at TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_approvals_status ON action_approvals(status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS action_callback_outbox (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            callback_url TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_error TEXT,
            locked_at TIMESTAMP,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            dedupe_key TEXT
        )
        """
    )
    # Existing installations created this table before callback deduplication.
    op.execute("ALTER TABLE action_callback_outbox ADD COLUMN IF NOT EXISTS dedupe_key TEXT")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_callback_outbox_status_next ON action_callback_outbox(status, next_attempt_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_callback_outbox_action_id ON action_callback_outbox(action_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_action_callback_outbox_dedupe_key ON action_callback_outbox(dedupe_key)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS action_callback_attempts (
            id TEXT PRIMARY KEY,
            outbox_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            attempt_no INTEGER NOT NULL,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            http_status INTEGER,
            duration_ms INTEGER,
            error_text TEXT,
            response_excerpt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_callback_attempts_action_id ON action_callback_attempts(action_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_callback_attempts_outbox_id ON action_callback_attempts(outbox_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS openclaw_capability_health_history (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            status TEXT NOT NULL,
            ready BOOLEAN NOT NULL DEFAULT FALSE,
            checks_json JSONB NOT NULL,
            metrics_json JSONB NOT NULL,
            alerts_json JSONB NOT NULL,
            window_minutes INTEGER NOT NULL DEFAULT 60,
            captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_openclaw_health_history_tenant_captured ON openclaw_capability_health_history(tenant_id, captured_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_ledger (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            tokens_in INTEGER DEFAULT 0,
            tokens_out INTEGER DEFAULT 0,
            cost NUMERIC(18,6) DEFAULT 0,
            tariff_id TEXT,
            month_key TEXT NOT NULL,
            meta_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_billing_ledger_action_id ON billing_ledger(action_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_billing_ledger_tenant_month ON billing_ledger(tenant_id, month_key)")


def downgrade():
    # Durable requests, approvals, callbacks and billing evidence survive rollback.
    pass
