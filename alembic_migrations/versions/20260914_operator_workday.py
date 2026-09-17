"""Shared Operator attachments and reviewed schedule snapshots; no CRM bookings."""
from alembic import op

revision = '20260914_operator_workday'
down_revision = '20260914_work_review'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE operatorconversations ADD COLUMN IF NOT EXISTS input_context_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute('''CREATE TABLE IF NOT EXISTS operator_attachments (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
        user_id TEXT NOT NULL REFERENCES users(id), conversation_id TEXT NOT NULL REFERENCES operatorconversations(id),
        request_key TEXT NOT NULL, content_hash TEXT NOT NULL, original_name TEXT NOT NULL,
        mime_type TEXT NOT NULL, storage_path TEXT NOT NULL, purpose TEXT NOT NULL DEFAULT 'unknown',
        extracted_text TEXT NOT NULL DEFAULT '', photo_asset_id TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(business_id,user_id,request_key), CHECK(purpose IN ('unknown','content','schedule','finance'))
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS operator_day_schedules (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id), day DATE NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, entries_json JSONB NOT NULL,
        source_json JSONB NOT NULL, updated_by TEXT NOT NULL REFERENCES users(id),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(business_id,day)
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS operator_schedule_history (
        action_id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL REFERENCES operator_day_schedules(id),
        business_id TEXT NOT NULL REFERENCES businesses(id), version INTEGER NOT NULL,
        before_json JSONB NOT NULL, after_json JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS operator_pilot_settings (
        business_id TEXT PRIMARY KEY REFERENCES businesses(id), recipient_user_id TEXT REFERENCES users(id),
        version INTEGER NOT NULL DEFAULT 1, updated_by TEXT NOT NULL REFERENCES users(id),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('ALTER TABLE journey_action_notification_deliveries ADD COLUMN IF NOT EXISTS dispatch_state TEXT')
    op.execute('ALTER TABLE journey_action_notification_deliveries ADD COLUMN IF NOT EXISTS attempted_at TIMESTAMPTZ')
    op.execute('ALTER TABLE journey_action_notification_deliveries ADD COLUMN IF NOT EXISTS provider_message_id TEXT')
    op.execute('''CREATE TABLE IF NOT EXISTS business_disk_connections (
        business_id TEXT PRIMARY KEY REFERENCES businesses(id), token_encrypted TEXT,
        version INTEGER NOT NULL DEFAULT 1, connected_by TEXT NOT NULL REFERENCES users(id),
        status TEXT NOT NULL DEFAULT 'connected', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_disk_oauth_states (
        state_hash TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
        user_id TEXT NOT NULL REFERENCES users(id), expires_at TIMESTAMPTZ NOT NULL,
        used_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS photo_disk_sync (
        photo_asset_id TEXT NOT NULL, business_id TEXT NOT NULL REFERENCES businesses(id),
        asset_version INTEGER NOT NULL, connection_version INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued', remote_path TEXT NOT NULL DEFAULT '',
        error_code TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(photo_asset_id,asset_version,connection_version)
    )''')


def downgrade():
    # Feature rollback is by allowlist; retain accepted input and history.
    pass
