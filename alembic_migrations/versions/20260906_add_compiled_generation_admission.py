"""Persist compiled generation admission before invoking a model."""
from alembic import op


revision = "20260906_008"
down_revision = "20260906_007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE IF NOT EXISTS compiled_generation_requests (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        business_id TEXT NOT NULL,
        blueprint_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        input_digest TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('generating', 'succeeded', 'failed')),
        result_version_id TEXT,
        error_code TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )""")
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_compiled_generation_request_key
        ON compiled_generation_requests(user_id, business_id, blueprint_id, idempotency_key)""")
    op.execute("""CREATE INDEX IF NOT EXISTS idx_compiled_generation_request_quota
        ON compiled_generation_requests(user_id, business_id, created_at DESC)""")


def downgrade():
    # Keep admission evidence during application rollback.
    pass
