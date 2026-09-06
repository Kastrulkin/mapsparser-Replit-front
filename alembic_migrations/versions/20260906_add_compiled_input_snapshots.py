"""Immutable, short-lived input snapshots for the read-only compiled pilot."""
from alembic import op

revision = "20260906_002"
down_revision = "20260906_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE IF NOT EXISTS compiled_input_snapshots (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL, user_id TEXT NOT NULL,
        blueprint_id TEXT NOT NULL, source_kind TEXT NOT NULL,
        source_name TEXT NOT NULL, schema_version TEXT NOT NULL,
        content_hash TEXT NOT NULL, input_json JSONB NOT NULL,
        row_count INTEGER NOT NULL CHECK (row_count BETWEEN 0 AND 200),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days'
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_compiled_snapshots_scope ON compiled_input_snapshots (business_id, user_id, expires_at)")
    op.execute("""CREATE OR REPLACE FUNCTION prevent_compiled_snapshot_mutation()
        RETURNS trigger AS $$ BEGIN
            RAISE EXCEPTION 'compiled input snapshots are immutable; create a new snapshot';
        END; $$ LANGUAGE plpgsql""")
    op.execute("DROP TRIGGER IF EXISTS trg_compiled_snapshot_immutable ON compiled_input_snapshots")
    op.execute("CREATE TRIGGER trg_compiled_snapshot_immutable BEFORE UPDATE ON compiled_input_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_compiled_snapshot_mutation()")


def downgrade():
    # Snapshot retention and run evidence survive a code rollback.
    pass
