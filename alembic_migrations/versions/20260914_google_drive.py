"""Optional Google Drive photo storage, independent of Yandex connections."""
from alembic import op
revision = '20260914_google_drive'
down_revision = '20260914_operator_workday'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS business_google_drive_connections (
        business_id TEXT PRIMARY KEY REFERENCES businesses(id), token_encrypted TEXT,
        version INTEGER NOT NULL DEFAULT 1, connected_by TEXT NOT NULL REFERENCES users(id),
        status TEXT NOT NULL DEFAULT 'connected', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_google_drive_oauth_states (
        state_hash TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
        user_id TEXT NOT NULL REFERENCES users(id), expires_at TIMESTAMPTZ NOT NULL,
        used_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS photo_google_drive_sync (
        photo_asset_id TEXT NOT NULL, business_id TEXT NOT NULL REFERENCES businesses(id),
        asset_version INTEGER NOT NULL, connection_version INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued', remote_path TEXT NOT NULL DEFAULT '',
        error_code TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(photo_asset_id,asset_version,connection_version)
    )''')

    op.execute("""CREATE TABLE IF NOT EXISTS google_drive_objects (
        business_id TEXT NOT NULL REFERENCES businesses(id), connection_version INTEGER NOT NULL,
        path TEXT NOT NULL, remote_id TEXT NOT NULL UNIQUE,
        PRIMARY KEY(business_id,connection_version,path)
    )""")

def downgrade():
    # Disable integration; preserve file identifiers and history.
    pass
