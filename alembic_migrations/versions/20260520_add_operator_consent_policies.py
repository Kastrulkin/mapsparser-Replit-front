"""add operator consent policies

Revision ID: 20260520_001
Revises: 20260515_001
Create Date: 2026-05-20 16:40:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260520_001"
down_revision = "20260515_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operatorconsentpolicies (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            action_key TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'ask_each_time',
            max_credits_per_action INTEGER,
            max_credits_per_day INTEGER,
            max_credits_per_month INTEGER,
            low_balance_warning_threshold INTEGER,
            created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            updated_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_operator_consent_mode CHECK (mode IN ('ask_each_time', 'auto_with_limits', 'disabled')),
            CONSTRAINT chk_operator_consent_limits_nonnegative CHECK (
                (max_credits_per_action IS NULL OR max_credits_per_action >= 0)
                AND (max_credits_per_day IS NULL OR max_credits_per_day >= 0)
                AND (max_credits_per_month IS NULL OR max_credits_per_month >= 0)
                AND (low_balance_warning_threshold IS NULL OR low_balance_warning_threshold >= 0)
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_operator_consent_business_action
        ON operatorconsentpolicies(business_id, action_key)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operator_consent_business_updated
        ON operatorconsentpolicies(business_id, updated_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_operator_consent_business_updated")
    op.execute("DROP INDEX IF EXISTS uq_operator_consent_business_action")
    op.execute("DROP TABLE IF EXISTS operatorconsentpolicies")
