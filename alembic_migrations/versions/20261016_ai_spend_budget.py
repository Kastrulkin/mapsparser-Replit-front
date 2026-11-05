"""Durable AI reservations and auditable request limits."""
from alembic import op
revision = '20261016_ai_spend_budget'
down_revision = '20261015_max_control'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS ai_spend_reservations (
        id TEXT PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL,
        task_key TEXT NOT NULL, business_id TEXT NOT NULL DEFAULT '',
        actor_user_id TEXT NOT NULL DEFAULT '', operation_id TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('reserved','completed','rejected','uncertain')),
        reserved_tokens BIGINT NOT NULL CHECK (reserved_tokens >= 0),
        actual_tokens BIGINT NOT NULL DEFAULT 0 CHECK (actual_tokens >= 0),
        error_code TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        settled_at TIMESTAMPTZ)''')
    op.execute('CREATE INDEX IF NOT EXISTS idx_ai_spend_provider_window ON ai_spend_reservations(provider,created_at)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_ai_spend_operation ON ai_spend_reservations(operation_id)')


def downgrade():
    # Financial audit rows are retained on rollback.
    pass
