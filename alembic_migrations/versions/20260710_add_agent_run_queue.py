"""add durable agent run queue fields

Revision ID: 20260710_001
Revises: 20260708_001
Create Date: 2026-07-10
"""

from alembic import op


revision = "20260710_001"
down_revision = "20260708_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS idempotency_key TEXT")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS queued_at TIMESTAMPTZ")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS billing_reservation_id TEXT")
    op.execute("ALTER TABLE agent_runs ALTER COLUMN started_at DROP NOT NULL")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_business_blueprint_idempotency
        ON agent_runs(business_id, blueprint_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_runs_queue_claim
        ON agent_runs(status, next_attempt_at, queued_at)
        WHERE status IN ('queued', 'retry_wait', 'running')
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_runs_queue_claim")
    op.execute("DROP INDEX IF EXISTS uq_agent_runs_business_blueprint_idempotency")
    op.execute(
        """
        UPDATE agent_runs
        SET started_at = COALESCE(started_at, queued_at, updated_at, NOW())
        WHERE started_at IS NULL
        """
    )
    op.execute("ALTER TABLE agent_runs ALTER COLUMN started_at SET NOT NULL")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS billing_reservation_id")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS max_attempts")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS attempt_count")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS next_attempt_at")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS heartbeat_at")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS queued_at")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS idempotency_key")
