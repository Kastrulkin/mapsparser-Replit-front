"""add yookassa billing core tables

Revision ID: 20260305_002
Revises: 20260305_001
Create Date: 2026-03-05 22:35:00.000000
"""

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260305_002"
down_revision = "20260305_001"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            text("SELECT to_regclass(:tbl) IS NOT NULL"),
            {"tbl": f"public.{name}"},
        ).scalar()
    )


def upgrade():
    if _has_table("users"):
        op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS credits_balance INTEGER NOT NULL DEFAULT 0")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL,
            tariff_id TEXT NOT NULL,
            pending_tariff_id TEXT,
            status TEXT NOT NULL DEFAULT 'blocked',
            period_start TIMESTAMP,
            next_billing_date TIMESTAMP,
            payment_method_id TEXT,
            last_payment_id TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            next_retry_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_subscriptions_status CHECK (status IN ('active', 'blocked', 'canceled'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_business_id ON subscriptions(business_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status_next_billing ON subscriptions(status, next_billing_date)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_business_id ON subscriptions(business_id) WHERE business_id IS NOT NULL")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            subscription_id TEXT REFERENCES subscriptions(id) ON DELETE SET NULL,
            delta INTEGER NOT NULL,
            reason TEXT NOT NULL,
            period_start TIMESTAMP,
            period_end TIMESTAMP,
            external_id TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_created ON credit_ledger(user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_credit_ledger_subscription ON credit_ledger(subscription_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_credit_ledger_external ON credit_ledger(external_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_attempts (
            id TEXT PRIMARY KEY,
            subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
            attempt_type TEXT NOT NULL,
            attempt_no INTEGER NOT NULL DEFAULT 0,
            scheduled_at TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'scheduled',
            payment_id TEXT,
            idempotency_key TEXT,
            amount_value NUMERIC(12,2),
            currency TEXT,
            error_message TEXT,
            metadata JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_billing_attempts_subscription ON billing_attempts(subscription_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_billing_attempts_status_sched ON billing_attempts(status, scheduled_at)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_attempts_payment_id ON billing_attempts(payment_id) WHERE payment_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_attempts_idempotency ON billing_attempts(idempotency_key)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS yookassa_webhook_events (
            id TEXT PRIMARY KEY,
            event_name TEXT NOT NULL,
            payment_id TEXT,
            payload JSONB,
            processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_yookassa_webhook_event_payment ON yookassa_webhook_events(event_name, payment_id) WHERE payment_id IS NOT NULL")


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_yookassa_webhook_event_payment")
    op.execute("DROP TABLE IF EXISTS yookassa_webhook_events")

    op.execute("DROP INDEX IF EXISTS uq_billing_attempts_idempotency")
    op.execute("DROP INDEX IF EXISTS uq_billing_attempts_payment_id")
    op.execute("DROP INDEX IF EXISTS idx_billing_attempts_status_sched")
    op.execute("DROP INDEX IF EXISTS idx_billing_attempts_subscription")
    op.execute("DROP TABLE IF EXISTS billing_attempts")

    op.execute("DROP INDEX IF EXISTS idx_credit_ledger_external")
    op.execute("DROP INDEX IF EXISTS idx_credit_ledger_subscription")
    op.execute("DROP INDEX IF EXISTS idx_credit_ledger_user_created")
    op.execute("DROP TABLE IF EXISTS credit_ledger")

    op.execute("DROP INDEX IF EXISTS uq_subscriptions_business_id")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_status_next_billing")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_business_id")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_user_id")
    op.execute("DROP TABLE IF EXISTS subscriptions")

    if _has_table("users"):
        op.execute("ALTER TABLE users DROP COLUMN IF EXISTS credits_balance")
