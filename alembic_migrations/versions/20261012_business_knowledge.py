"""Versioned business knowledge, isolated editors and private document references."""
from alembic import op

revision = '20261012_business_knowledge'
down_revision = '20261009_business_chat'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS business_knowledge_records (
        id TEXT PRIMARY KEY, scope_type TEXT NOT NULL CHECK(scope_type IN ('business','network')),
        scope_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('field','value','rule','document')),
        record_key TEXT NOT NULL, payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        audience TEXT NOT NULL DEFAULT 'team' CHECK(audience IN ('team','management')),
        archived BOOLEAN NOT NULL DEFAULT FALSE, version INTEGER NOT NULL DEFAULT 1,
        created_by TEXT NOT NULL, updated_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(scope_type,scope_id,kind,record_key))''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_knowledge_history (
        id TEXT PRIMARY KEY, record_id TEXT NOT NULL REFERENCES business_knowledge_records(id),
        actor_id TEXT NOT NULL, before_json JSONB, after_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_knowledge_editors (
        scope_type TEXT NOT NULL CHECK(scope_type IN ('business','network')), scope_id TEXT NOT NULL,
        user_id TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT TRUE, version INTEGER NOT NULL DEFAULT 1,
        granted_by TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(scope_type,scope_id,user_id))''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_knowledge_receipts (
        scope_type TEXT NOT NULL, scope_id TEXT NOT NULL, actor_id TEXT NOT NULL,
        request_id TEXT NOT NULL, request_hash TEXT NOT NULL, result_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(scope_type,scope_id,actor_id,request_id))''')
    op.execute('CREATE INDEX IF NOT EXISTS idx_business_knowledge_scope ON business_knowledge_records(scope_type,scope_id,kind)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_business_knowledge_history ON business_knowledge_history(record_id,created_at)')


def downgrade():
    # Application rollback must retain user records, versions and private file references.
    pass
