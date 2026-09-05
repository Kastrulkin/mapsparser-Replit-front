"""add fenced leases for durable runtime jobs

Revision ID: 20260905_001
Revises: 20260902_002
Create Date: 2026-09-05
"""

from alembic import op


revision = "20260905_001"
down_revision = "20260902_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE operator_async_jobs ADD COLUMN IF NOT EXISTS lease_token TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_operator_async_jobs_running_lease "
        "ON operator_async_jobs(status, heartbeat_at) WHERE status = 'running'"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_operator_async_jobs_running_lease")
    op.execute("ALTER TABLE operator_async_jobs DROP COLUMN IF EXISTS lease_token")
