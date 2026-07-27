"""add durable operator async jobs

Revision ID: 20260727_002
Revises: 20260727_001
"""

from alembic import op


revision = "20260727_002"
down_revision = "20260727_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_async_jobs (
            id TEXT PRIMARY KEY,
            action_id TEXT REFERENCES operatoractions(id) ON DELETE SET NULL,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            progress INTEGER NOT NULL DEFAULT 0,
            stage TEXT NOT NULL DEFAULT '',
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_text TEXT,
            idempotency_key TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            heartbeat_at TIMESTAMPTZ,
            next_attempt_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            CONSTRAINT ck_operator_async_jobs_status CHECK (
                status IN ('queued', 'running', 'waiting_for_review', 'completed', 'failed', 'cancelled')
            ),
            CONSTRAINT ck_operator_async_jobs_progress CHECK (progress BETWEEN 0 AND 100),
            CONSTRAINT uq_operator_async_jobs_user_idempotency UNIQUE (user_id, idempotency_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_operator_async_jobs_queue "
        "ON operator_async_jobs(status, next_attempt_at, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_operator_async_jobs_business_updated "
        "ON operator_async_jobs(business_id, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_operator_async_jobs_action "
        "ON operator_async_jobs(action_id)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_operator_async_jobs_action")
    op.execute("DROP INDEX IF EXISTS idx_operator_async_jobs_business_updated")
    op.execute("DROP INDEX IF EXISTS idx_operator_async_jobs_queue")
    op.execute("DROP TABLE IF EXISTS operator_async_jobs")
