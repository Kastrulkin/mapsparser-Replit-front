"""Business chat change receipts and distinct admin/master membership roles."""
from alembic import op

revision = '20261009_business_chat'
down_revision = '20261005_manual_access_grants'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('business_members', 'network_members'):
        op.execute('ALTER TABLE ' + table + ' DROP CONSTRAINT IF EXISTS ck_' + table + '_role')
        op.execute('ALTER TABLE ' + table + ' ADD CONSTRAINT ck_' + table + "_role CHECK (role IN ('manager','member','viewer','admin','master'))")
    op.execute("""CREATE TABLE IF NOT EXISTS business_change_receipts (
        action_id TEXT PRIMARY KEY, actor_user_id TEXT NOT NULL REFERENCES users(id),
        anchor_business_id TEXT NOT NULL REFERENCES businesses(id),
        payload_hash TEXT NOT NULL, result_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    op.execute("""CREATE TABLE IF NOT EXISTS business_team_invitations (
        action_id TEXT PRIMARY KEY REFERENCES business_change_receipts(action_id),
        recipient_user_id TEXT NOT NULL REFERENCES users(id),
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent','failed')),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")


def downgrade():
    # Refuse to silently expand a master's rights through a role conversion.
    for table in ('business_members', 'network_members'):
        op.execute('ALTER TABLE ' + table + ' DROP CONSTRAINT IF EXISTS ck_' + table + '_role')
        op.execute('ALTER TABLE ' + table + ' ADD CONSTRAINT ck_' + table + "_role CHECK (role IN ('manager','member','viewer'))")
    op.execute('DROP TABLE IF EXISTS business_team_invitations')
    op.execute('DROP TABLE IF EXISTS business_change_receipts')
