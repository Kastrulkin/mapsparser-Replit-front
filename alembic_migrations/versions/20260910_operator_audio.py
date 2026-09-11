"""Operator request deduplication and private voice assets."""
from alembic import op
revision = '20260910_001'
down_revision = '20260909_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")
    op.execute('''CREATE TABLE IF NOT EXISTS operator_chat_requests (
        user_id TEXT NOT NULL, business_id TEXT NOT NULL, channel TEXT NOT NULL,
        request_id TEXT NOT NULL, input_hash TEXT NOT NULL, result_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(user_id,business_id,channel,request_id))''')
    op.execute('''CREATE TABLE IF NOT EXISTS operator_audio_assets (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, business_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL REFERENCES operatorconversations(id),
        kind TEXT NOT NULL CHECK (kind IN ('transcription','speech')),
        channel TEXT NOT NULL, path TEXT, format TEXT, duration DOUBLE PRECISION,
        status TEXT NOT NULL DEFAULT 'queued', transcript TEXT, corrected_text TEXT,
        message_id TEXT, job_id TEXT, request_id TEXT NOT NULL,
        provider_operation_id TEXT, metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
        UNIQUE(user_id,business_id,channel,kind,request_id))''')
    op.execute('CREATE INDEX IF NOT EXISTS idx_operator_audio_expiry ON operator_audio_assets(expires_at) WHERE path IS NOT NULL')


def downgrade():
    # Preserve journals and history on application rollback.
    pass
