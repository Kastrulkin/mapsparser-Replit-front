"""Fence approved Google Sheets provider handoffs.

Revision ID: 20260907_001
Revises: 20260906_012
"""

from alembic import op


revision = "20260907_001"
down_revision = "20260906_012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS bound_run_id TEXT")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS bound_step_id TEXT")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS bound_approval_id TEXT")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS request_hash TEXT")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS provider_state TEXT NOT NULL DEFAULT 'not_queued'")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS provider_lease_token TEXT")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS provider_lease_expires_at TIMESTAMPTZ")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS provider_attempt_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE agent_sheet_operation_requests ADD COLUMN IF NOT EXISTS provider_result_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_sheet_provider_claim ON agent_sheet_operation_requests (apply_state, updated_at, created_at) WHERE provider_write_performed = FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_sheet_provider_binding ON agent_sheet_operation_requests (bound_run_id, bound_step_id, bound_approval_id)")


def downgrade():
    # Provider journals are retained so a rollback cannot make an ambiguous
    # external write invisible. The previous code ignores these columns.
    pass
