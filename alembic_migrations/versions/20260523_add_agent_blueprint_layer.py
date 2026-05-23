"""add agent blueprint layer

Revision ID: 20260523_001
Revises: 20260521_001
Create Date: 2026-05-23
"""

from alembic import op


revision = "20260523_001"
down_revision = "20260521_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_blueprints (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by_user_id TEXT NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_blueprint_versions (
            id TEXT PRIMARY KEY,
            blueprint_id TEXT NOT NULL REFERENCES agent_blueprints(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL,
            goal TEXT NOT NULL,
            inputs_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            steps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            persona_agent_id TEXT,
            capability_allowlist_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            approval_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_by_user_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY,
            blueprint_id TEXT NOT NULL REFERENCES agent_blueprints(id) ON DELETE CASCADE,
            blueprint_version_id TEXT NOT NULL REFERENCES agent_blueprint_versions(id) ON DELETE RESTRICT,
            business_id TEXT NOT NULL,
            status TEXT NOT NULL,
            input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_text TEXT,
            created_by_user_id TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_run_steps (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
            step_index INTEGER NOT NULL,
            step_key TEXT NOT NULL,
            step_type TEXT NOT NULL,
            status TEXT NOT NULL,
            input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_text TEXT,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_artifacts (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
            step_id TEXT REFERENCES agent_run_steps(id) ON DELETE SET NULL,
            artifact_type TEXT NOT NULL,
            title TEXT NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_approvals (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
            step_id TEXT REFERENCES agent_run_steps(id) ON DELETE SET NULL,
            status TEXT NOT NULL,
            approval_type TEXT NOT NULL,
            title TEXT NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            requested_by_user_id TEXT NOT NULL,
            decided_by_user_id TEXT,
            decision_reason TEXT,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decided_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_blueprints_business ON agent_blueprints(business_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_blueprints_status ON agent_blueprints(status)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_blueprint_versions_number ON agent_blueprint_versions(blueprint_id, version_number)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_blueprint_versions_blueprint ON agent_blueprint_versions(blueprint_id, version_number DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_business_created ON agent_runs(business_id, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_blueprint_created ON agent_runs(blueprint_id, started_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_run_steps_order ON agent_run_steps(run_id, step_index)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_artifacts_run ON agent_artifacts(run_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_approvals_run_status ON agent_approvals(run_id, status)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_approvals_run_status")
    op.execute("DROP INDEX IF EXISTS idx_agent_artifacts_run")
    op.execute("DROP INDEX IF EXISTS uq_agent_run_steps_order")
    op.execute("DROP INDEX IF EXISTS idx_agent_runs_status")
    op.execute("DROP INDEX IF EXISTS idx_agent_runs_blueprint_created")
    op.execute("DROP INDEX IF EXISTS idx_agent_runs_business_created")
    op.execute("DROP INDEX IF EXISTS idx_agent_blueprint_versions_blueprint")
    op.execute("DROP INDEX IF EXISTS uq_agent_blueprint_versions_number")
    op.execute("DROP INDEX IF EXISTS idx_agent_blueprints_status")
    op.execute("DROP INDEX IF EXISTS idx_agent_blueprints_business")
    op.execute("DROP TABLE IF EXISTS agent_approvals")
    op.execute("DROP TABLE IF EXISTS agent_artifacts")
    op.execute("DROP TABLE IF EXISTS agent_run_steps")
    op.execute("DROP TABLE IF EXISTS agent_runs")
    op.execute("DROP TABLE IF EXISTS agent_blueprint_versions")
    op.execute("DROP TABLE IF EXISTS agent_blueprints")
