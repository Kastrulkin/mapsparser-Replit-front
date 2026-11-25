"""Keep the first setup with the business across chat sessions."""
from alembic import op

revision = '20261122_initial_business_setup'
down_revision = '20261105_prepared_cabinet'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS initial_business_setups (
        business_id TEXT PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
        lead_id TEXT UNIQUE,
        origin TEXT NOT NULL CHECK (origin IN ('registration','staff','owner')),
        provisional BOOLEAN NOT NULL DEFAULT FALSE,
        revision INTEGER NOT NULL DEFAULT 1,
        data JSONB NOT NULL DEFAULT '{}'::jsonb,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')


def downgrade():
    op.execute('DROP TABLE IF EXISTS initial_business_setups')
