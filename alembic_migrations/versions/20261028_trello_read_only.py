"""Read-only Trello OAuth attempts and explicitly selected board snapshots."""
from alembic import op

revision = '20261028_trello_read_only'
down_revision = '20261016_ai_spend_budget'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS trello_oauth_attempts (
        state_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL,
        business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL, session_id TEXT NOT NULL,
        verifier_encrypted TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
        consumed_at TIMESTAMPTZ, cancelled BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_trello_business_connection
        ON externalbusinessaccounts(business_id) WHERE source='trello' ''')
    op.execute('''CREATE TABLE IF NOT EXISTS trello_board_snapshots (
        account_id TEXT NOT NULL REFERENCES externalbusinessaccounts(id) ON DELETE CASCADE,
        board_id TEXT NOT NULL, board_name TEXT NOT NULL,
        snapshot_json JSONB, last_sync_at TIMESTAMPTZ,
        PRIMARY KEY(account_id,board_id))''')


def downgrade():
    op.execute('DROP TABLE IF EXISTS trello_board_snapshots')
    op.execute('DROP INDEX IF EXISTS uq_trello_business_connection')
    op.execute('DROP TABLE IF EXISTS trello_oauth_attempts')
