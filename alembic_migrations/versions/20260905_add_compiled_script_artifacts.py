"""add immutable compiled script artifacts

Revision ID: 20260905_002
Revises: 20260905_001
Create Date: 2026-09-05
"""
from alembic import op

revision = "20260905_002"
down_revision = "20260905_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE agent_blueprint_versions
        ADD COLUMN IF NOT EXISTS compiled_artifact_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS compiled_artifact_hash TEXT,
        ADD COLUMN IF NOT EXISTS compiled_state TEXT NOT NULL DEFAULT 'legacy',
        ADD COLUMN IF NOT EXISTS compiled_preview_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS compiled_approved_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS compiled_approved_by_user_id TEXT""")
    op.execute("""DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
            WHERE conname='ck_agent_blueprint_versions_compiled_state'
              AND conrelid='agent_blueprint_versions'::regclass) THEN
            ALTER TABLE agent_blueprint_versions ADD CONSTRAINT ck_agent_blueprint_versions_compiled_state
                CHECK (compiled_state IN ('legacy','draft','checking','needs_fix','ready_approval','approved','active','paused','replaced')) NOT VALID;
        END IF;
    END $$""")
    op.execute("ALTER TABLE agent_blueprint_versions VALIDATE CONSTRAINT ck_agent_blueprint_versions_compiled_state")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_blueprint_versions_compiled_hash ON agent_blueprint_versions(compiled_artifact_hash) WHERE compiled_artifact_hash IS NOT NULL")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_compiled_script_artifact_mutation()
        RETURNS trigger AS $$ BEGIN
        IF OLD.compiled_artifact_hash IS NOT NULL AND
           (NEW.compiled_artifact_json IS DISTINCT FROM OLD.compiled_artifact_json OR NEW.compiled_artifact_hash IS DISTINCT FROM OLD.compiled_artifact_hash) THEN
            RAISE EXCEPTION 'compiled script artifacts are immutable; create a new version';
        END IF;
        RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    op.execute("DROP TRIGGER IF EXISTS trg_compiled_script_artifact_immutable ON agent_blueprint_versions")
    op.execute("""CREATE TRIGGER trg_compiled_script_artifact_immutable BEFORE UPDATE ON agent_blueprint_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_compiled_script_artifact_mutation()""")


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_compiled_script_artifact_immutable ON agent_blueprint_versions")
    op.execute("DROP FUNCTION IF EXISTS prevent_compiled_script_artifact_mutation()")
    op.execute("DROP INDEX IF EXISTS idx_agent_blueprint_versions_compiled_hash")
    op.execute("ALTER TABLE agent_blueprint_versions DROP CONSTRAINT IF EXISTS ck_agent_blueprint_versions_compiled_state")
    op.execute("""ALTER TABLE agent_blueprint_versions DROP COLUMN IF EXISTS compiled_approved_by_user_id,
        DROP COLUMN IF EXISTS compiled_approved_at, DROP COLUMN IF EXISTS compiled_preview_json,
        DROP COLUMN IF EXISTS compiled_state, DROP COLUMN IF EXISTS compiled_artifact_hash,
        DROP COLUMN IF EXISTS compiled_artifact_json""")
