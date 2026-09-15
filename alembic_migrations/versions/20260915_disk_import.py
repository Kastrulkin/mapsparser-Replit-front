"""Owner-scoped inbound media, resumable directory scans and external videos."""
from alembic import op
revision='20260915_disk_import'
down_revision='20260915_storage_oauth'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS disk_import_credentials (
        id TEXT PRIMARY KEY, client_email TEXT NOT NULL, secret_encrypted TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, updated_by TEXT NOT NULL REFERENCES users(id), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS disk_import_sources (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id), provider TEXT NOT NULL CHECK(provider IN ('google','yandex')),
        root_id TEXT NOT NULL, root_name TEXT NOT NULL DEFAULT '', root_url TEXT NOT NULL DEFAULT '',
        connected_by TEXT NOT NULL REFERENCES users(id), credential_identity TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL DEFAULT 'awaiting_proof',
        challenge_hash TEXT, challenge_expires_at TIMESTAMPTZ, challenge_used_at TIMESTAMPTZ,
        scan_id TEXT, scan_sequence INTEGER NOT NULL DEFAULT 0, pending_json JSONB NOT NULL DEFAULT '[]', visited_json JSONB NOT NULL DEFAULT '[]',
        next_scan_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_checked_at TIMESTAMPTZ, error_code TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS disk_import_google_root ON disk_import_sources(root_id) WHERE provider='google' AND state NOT IN ('disconnected','awaiting_proof')")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS disk_import_business_provider ON disk_import_sources(business_id,provider) WHERE state!='disconnected'")
    op.execute('''CREATE TABLE IF NOT EXISTS disk_import_files (
        source_id TEXT NOT NULL REFERENCES disk_import_sources(id), external_id TEXT NOT NULL,
        revision TEXT NOT NULL, imported_revision TEXT, name TEXT NOT NULL, kind TEXT NOT NULL,
        metadata_json JSONB NOT NULL DEFAULT '{}', last_seen_scan TEXT NOT NULL,
        available BOOLEAN NOT NULL DEFAULT TRUE, status TEXT NOT NULL DEFAULT 'pending', error_code TEXT,
        photo_asset_id TEXT, video_id TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(source_id,external_id)
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS disk_import_revisions (
        source_id TEXT NOT NULL REFERENCES disk_import_sources(id), external_id TEXT NOT NULL, revision TEXT NOT NULL,
        photo_asset_id TEXT, video_id TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(source_id,external_id,revision)
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS external_video_assets (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id), source_id TEXT NOT NULL REFERENCES disk_import_sources(id),
        external_id TEXT NOT NULL, revision TEXT NOT NULL, name TEXT NOT NULL, mime_type TEXT NOT NULL,
        size_bytes BIGINT NOT NULL DEFAULT 0, duration_ms BIGINT, original_url TEXT NOT NULL,
        available BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(source_id,external_id,revision)
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS content_external_video_usage (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id), item_id TEXT NOT NULL REFERENCES contentplanitems(id),
        video_id TEXT NOT NULL REFERENCES external_video_assets(id), selected_by TEXT NOT NULL REFERENCES users(id),
        active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute("CREATE INDEX IF NOT EXISTS disk_import_job_fairness ON operator_async_jobs(business_id,updated_at DESC) WHERE kind IN ('disk_import_scan','disk_import_file') AND status IN ('running','completed','failed')")
    op.execute('CREATE INDEX IF NOT EXISTS disk_import_due ON disk_import_sources(next_scan_at) WHERE state=\'active\'')


def downgrade():
    # Disable the business allowlist. Preserve media and selected-content history.
    pass
