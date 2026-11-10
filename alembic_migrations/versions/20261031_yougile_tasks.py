"""Business-scoped YouGile settings and durable external-write attempts."""
from alembic import op

revision = '20261031_yougile_tasks'
down_revision = '20261105_prepared_cabinet'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_yougile_business_connection
        ON externalbusinessaccounts(business_id) WHERE source='yougile'""")
    op.execute('''CREATE TABLE IF NOT EXISTS yougile_connections (
        account_id TEXT PRIMARY KEY REFERENCES externalbusinessaccounts(id) ON DELETE CASCADE,
        project_id TEXT,board_id TEXT,column_id TEXT,selection_json JSONB NOT NULL DEFAULT '{}',
        version INTEGER NOT NULL DEFAULT 1,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    op.execute('''CREATE TABLE IF NOT EXISTS yougile_task_requests (
        request_id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES externalbusinessaccounts(id),
        user_id TEXT NOT NULL,payload_hash TEXT NOT NULL,status TEXT NOT NULL,
        external_task_id TEXT,result_json JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')


def downgrade():
    op.execute('DROP TABLE IF EXISTS yougile_task_requests')
    op.execute('DROP TABLE IF EXISTS yougile_connections')
    op.execute('DROP INDEX IF EXISTS uq_yougile_business_connection')
