"""add unified checkout sessions

Revision ID: 20260422_002
Revises: 20260422_001
Create Date: 2026-04-22 20:45:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260422_002"
down_revision = "20260422_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkout_sessions (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            channel TEXT NOT NULL,
            entry_point TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            tariff_id TEXT NOT NULL,
            amount NUMERIC(12,2) NOT NULL,
            currency TEXT NOT NULL DEFAULT 'RUB',
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL,
            telegram_id TEXT,
            telegram_username TEXT,
            telegram_name TEXT,
            email TEXT,
            phone TEXT,
            maps_url TEXT,
            normalized_maps_url TEXT,
            audit_slug TEXT,
            audit_public_url TEXT,
            competitor_maps_url TEXT,
            competitor_audit_url TEXT,
            provider_invoice_id TEXT,
            provider_payment_id TEXT,
            provider_status TEXT,
            source TEXT,
            payload_json JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP,
            completed_at TIMESTAMP,
            CONSTRAINT chk_checkout_sessions_status
                CHECK (status IN ('created', 'checkout_created', 'paid', 'account_linked', 'business_linked', 'completed', 'failed', 'expired')),
            CONSTRAINT chk_checkout_sessions_channel
                CHECK (channel IN ('telegram', 'web')),
            CONSTRAINT chk_checkout_sessions_provider
                CHECK (provider IN ('telegram_crypto', 'yookassa', 'stripe')),
            CONSTRAINT chk_checkout_sessions_entry_point
                CHECK (entry_point IN ('public_audit', 'registered_paywall', 'pricing_page', 'telegram_guest'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_sessions_status ON checkout_sessions(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_sessions_entry_point ON checkout_sessions(entry_point)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_sessions_user_id ON checkout_sessions(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_sessions_business_id ON checkout_sessions(business_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_sessions_telegram_id ON checkout_sessions(telegram_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_checkout_sessions_email ON checkout_sessions(email)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_checkout_sessions_provider_payment
        ON checkout_sessions(provider, provider_payment_id)
        WHERE provider_payment_id IS NOT NULL
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_checkout_sessions_provider_payment")
    op.execute("DROP INDEX IF EXISTS idx_checkout_sessions_email")
    op.execute("DROP INDEX IF EXISTS idx_checkout_sessions_telegram_id")
    op.execute("DROP INDEX IF EXISTS idx_checkout_sessions_business_id")
    op.execute("DROP INDEX IF EXISTS idx_checkout_sessions_user_id")
    op.execute("DROP INDEX IF EXISTS idx_checkout_sessions_entry_point")
    op.execute("DROP INDEX IF EXISTS idx_checkout_sessions_status")
    op.execute("DROP TABLE IF EXISTS checkout_sessions")
