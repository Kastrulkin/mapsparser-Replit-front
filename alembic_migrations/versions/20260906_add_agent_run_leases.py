"""Fence agent-run workers and pin immutable input snapshots.

Revision ID: 20260906_001
Revises: 20260905_004
Create Date: 2026-09-06
"""

from alembic import op


revision = "20260906_001"
down_revision = "20260905_004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS lease_token TEXT")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS input_snapshot_id TEXT")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS input_snapshot_hash TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_running_lease "
        "ON agent_runs(status, heartbeat_at) WHERE status = 'running'"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_runs_running_lease")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS input_snapshot_hash")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS input_snapshot_id")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS lease_token")
