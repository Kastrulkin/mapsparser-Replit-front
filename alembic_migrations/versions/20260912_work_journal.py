"""Work journal, scoped staff links and versioned upsell policies."""
from alembic import op
revision = '20260912_work_journal'
down_revision = '20260912_finance_daily'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS business_work_journal (
        id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),user_id TEXT NOT NULL REFERENCES users(id),
        channel TEXT NOT NULL,message_id TEXT,request_key TEXT NOT NULL,original_text TEXT NOT NULL,
        facts_json JSONB NOT NULL DEFAULT '{}',booking_id TEXT,service_id TEXT,task_id TEXT,
        occurred_at TIMESTAMPTZ NOT NULL,version INTEGER NOT NULL DEFAULT 1,is_voided BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(business_id,user_id,request_key))''')
    op.execute('CREATE INDEX IF NOT EXISTS work_journal_scope ON business_work_journal(business_id,occurred_at DESC)')
    op.execute('''CREATE TABLE IF NOT EXISTS business_work_history (
        id TEXT PRIMARY KEY,business_id TEXT NOT NULL,target_id TEXT NOT NULL,kind TEXT NOT NULL,request_key TEXT NOT NULL,
        user_id TEXT NOT NULL,channel TEXT NOT NULL,before_json JSONB,after_json JSONB,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(business_id,request_key))''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_upsell_policies (
        business_id TEXT PRIMARY KEY REFERENCES businesses(id),version INTEGER NOT NULL DEFAULT 0,
        rules_json JSONB NOT NULL DEFAULT '[]',updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    op.execute('ALTER TABLE business_upsell_policies ADD COLUMN IF NOT EXISTS matrix_json JSONB')
    op.execute('''CREATE TABLE IF NOT EXISTS masters (id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),name TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    op.execute('ALTER TABLE masters ADD COLUMN IF NOT EXISTS business_id TEXT REFERENCES businesses(id)')
    op.execute('ALTER TABLE IF EXISTS bookings ADD COLUMN IF NOT EXISTS master_id TEXT')
    op.execute('''CREATE TABLE IF NOT EXISTS business_master_bindings (
        business_id TEXT NOT NULL REFERENCES businesses(id),user_id TEXT NOT NULL REFERENCES users(id),master_id TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(business_id,user_id))''')
    op.execute('ALTER TABLE averageticketevents ADD COLUMN IF NOT EXISTS journal_id TEXT')
    op.execute('ALTER TABLE averageticketevents ADD COLUMN IF NOT EXISTS is_voided BOOLEAN NOT NULL DEFAULT FALSE')
    op.execute('CREATE UNIQUE INDEX IF NOT EXISTS average_ticket_journal_event ON averageticketevents(journal_id) WHERE journal_id IS NOT NULL')


def downgrade():
    # Preserve observations, confirmed policies and audit history on application rollback.
    pass
