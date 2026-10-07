"""Add audit records for superadmin grants after offline payment.

Revision ID: 20261005_manual_access_grants
Revises: 20260907_001
Create Date: 2026-10-05
"""

from alembic import op


revision = "20261005_manual_access_grants"
down_revision = "20260907_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """CREATE TABLE IF NOT EXISTS manual_access_grants (
            id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL UNIQUE,
            target_type TEXT NOT NULL CHECK (target_type IN ('business', 'network')),
            target_id TEXT NOT NULL,
            business_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            granted_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            tariff_id TEXT NOT NULL,
            tier TEXT NOT NULL,
            credit_amount INTEGER NOT NULL DEFAULT 0 CHECK (credit_amount >= 0),
            balance_before INTEGER NOT NULL DEFAULT 0,
            balance_after INTEGER NOT NULL DEFAULT 0,
            payment_amount_rub NUMERIC(12, 2) NOT NULL CHECK (payment_amount_rub > 0),
            currency TEXT NOT NULL DEFAULT 'RUB' CHECK (currency = 'RUB'),
            payment_reference TEXT,
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_manual_access_grants_target_created ON manual_access_grants(target_type, target_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_manual_access_grants_user_created ON manual_access_grants(user_id, created_at DESC)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_manual_access_grants_user_created")
    op.execute("DROP INDEX IF EXISTS idx_manual_access_grants_target_created")
    op.execute("DROP TABLE IF EXISTS manual_access_grants")
