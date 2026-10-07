"""Versioned daily finance reporting, never synthetic transaction rows."""
from alembic import op

revision = '20260912_finance_daily'
down_revision = '20260911_card_growth_cycles'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS business_finance_settings (
        business_id TEXT PRIMARY KEY REFERENCES businesses(id), currency TEXT, timezone TEXT,
        version INTEGER NOT NULL DEFAULT 1, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    op.execute('''CREATE TABLE IF NOT EXISTS finance_daily_summaries (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id), date DATE NOT NULL,
        currency TEXT NOT NULL, values_json JSONB NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1,
        is_voided BOOLEAN NOT NULL DEFAULT FALSE, user_id TEXT NOT NULL REFERENCES users(id),
        channel TEXT NOT NULL, message_ref TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(business_id,date,currency))''')
    op.execute('''CREATE TABLE IF NOT EXISTS finance_daily_events (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id), target_id TEXT NOT NULL,
        kind TEXT NOT NULL, action_id TEXT NOT NULL UNIQUE, before_json JSONB, after_json JSONB,
        user_id TEXT NOT NULL, channel TEXT NOT NULL, message_ref TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    op.execute('CREATE INDEX IF NOT EXISTS finance_daily_event_target ON finance_daily_events(business_id,target_id,created_at)')
    for table in ('financialtransactions','finance_entries'):
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS currency TEXT')
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS is_voided BOOLEAN NOT NULL DEFAULT FALSE')
    op.execute('ALTER TABLE finance_service_metrics ADD COLUMN IF NOT EXISTS currency TEXT')
    op.execute('ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS receipt_id TEXT')
    op.execute('ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS sale_type TEXT')
    op.execute('ALTER TABLE financialtransactions ADD COLUMN IF NOT EXISTS has_upsell BOOLEAN')
    op.execute('ALTER TABLE financialtransactions DROP CONSTRAINT IF EXISTS financialtransactions_transaction_type_check')
    op.execute("ALTER TABLE financialtransactions ADD CONSTRAINT financialtransactions_transaction_type_check CHECK (transaction_type IN ('income','expense','refund')) NOT VALID")
    op.execute('ALTER TABLE financialtransactions VALIDATE CONSTRAINT financialtransactions_transaction_type_check')


def downgrade():
    # Existing money/currency columns and financial history must survive rollback.
    pass
