"""Service creation and independent map distribution state."""
from alembic import op

revision = '20260911_operator_services'
down_revision = '20260911_partner_agreements'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE userservices ADD COLUMN IF NOT EXISTS currency TEXT')
    op.execute('''CREATE TABLE IF NOT EXISTS operator_service_distribution (
        id TEXT PRIMARY KEY,
        business_id TEXT NOT NULL REFERENCES businesses(id),
        user_id TEXT NOT NULL REFERENCES users(id),
        service_id TEXT NOT NULL REFERENCES userservices(id),
        request_key TEXT NOT NULL,
        google_status TEXT NOT NULL DEFAULT 'not_prepared',
        google_preview JSONB NOT NULL DEFAULT '{}',
        google_error TEXT,
        manual_task_id UUID,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(business_id,user_id,request_key)
    )''')


def downgrade():
    op.execute('DROP TABLE IF EXISTS operator_service_distribution')
    # currency predates this migration on production; never remove existing data.
