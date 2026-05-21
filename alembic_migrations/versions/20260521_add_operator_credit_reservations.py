"""add operator credit reservations

Revision ID: 20260521_001
Revises: 20260520_001
Create Date: 2026-05-21 18:10:00.000000
"""

from alembic import op
from sqlalchemy import text


revision = "20260521_001"
down_revision = "20260520_001"
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
    if not _has_table("users") or not _has_table("businesses"):
        return

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operatorcreditreservations (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action_key TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'reserved',
            estimated_credits INTEGER NOT NULL DEFAULT 0,
            reserved_credits INTEGER NOT NULL DEFAULT 0,
            charged_credits INTEGER NOT NULL DEFAULT 0,
            released_credits INTEGER NOT NULL DEFAULT 0,
            credit_ledger_id TEXT REFERENCES credit_ledger(id) ON DELETE SET NULL,
            metadata JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finalized_at TIMESTAMP,
            CONSTRAINT chk_operator_credit_reservation_status
                CHECK (status IN ('reserved', 'charged', 'released', 'failed')),
            CONSTRAINT chk_operator_credit_reservation_nonnegative
                CHECK (
                    estimated_credits >= 0
                    AND reserved_credits >= 0
                    AND charged_credits >= 0
                    AND released_credits >= 0
                )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_operator_credit_reservations_business_status ON operatorcreditreservations(business_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_operator_credit_reservations_user_created ON operatorcreditreservations(user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_operator_credit_reservations_action ON operatorcreditreservations(action_key)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_operator_credit_reservations_idempotency
        ON operatorcreditreservations(business_id, action_key, idempotency_key)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_operator_credit_reservations_idempotency")
    op.execute("DROP INDEX IF EXISTS idx_operator_credit_reservations_action")
    op.execute("DROP INDEX IF EXISTS idx_operator_credit_reservations_user_created")
    op.execute("DROP INDEX IF EXISTS idx_operator_credit_reservations_business_status")
    op.execute("DROP TABLE IF EXISTS operatorcreditreservations")
