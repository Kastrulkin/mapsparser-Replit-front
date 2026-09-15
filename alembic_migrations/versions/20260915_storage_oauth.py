"""Encrypted platform OAuth applications for optional photo storage."""
from alembic import op
revision='20260915_storage_oauth'
down_revision='20260914_google_drive'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS storage_oauth_apps (
        provider TEXT PRIMARY KEY CHECK(provider IN ('yandex','google')),
        client_id TEXT NOT NULL, secret_encrypted TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, updated_by TEXT NOT NULL REFERENCES users(id),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')


def downgrade():
    # Preserve encrypted configuration on rollback; old deployments ignore this table.
    pass
