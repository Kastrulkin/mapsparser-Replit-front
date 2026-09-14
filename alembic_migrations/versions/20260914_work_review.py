"""Review employee observations and link existing actions without duplicating tasks."""
from alembic import op
revision='20260914_work_review'
down_revision='20260914_riderra_runs'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("ALTER TABLE business_work_journal ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'other'")
    op.execute("ALTER TABLE business_work_journal ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'new'")
    op.execute('ALTER TABLE business_work_journal ADD COLUMN IF NOT EXISTS assigned_to TEXT REFERENCES users(id)')
    op.execute("ALTER TABLE business_work_journal ADD COLUMN IF NOT EXISTS decision TEXT NOT NULL DEFAULT ''")
    op.execute('ALTER TABLE business_work_journal ADD COLUMN IF NOT EXISTS urgent BOOLEAN NOT NULL DEFAULT FALSE')
    op.execute('''CREATE TABLE IF NOT EXISTS business_work_reviewers (
        business_id TEXT NOT NULL REFERENCES businesses(id),user_id TEXT NOT NULL REFERENCES users(id),
        enabled BOOLEAN NOT NULL DEFAULT TRUE,version INTEGER NOT NULL DEFAULT 1,granted_by TEXT NOT NULL REFERENCES users(id),
        PRIMARY KEY(business_id,user_id))''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_work_links (
        business_id TEXT NOT NULL REFERENCES businesses(id),entry_id TEXT NOT NULL REFERENCES business_work_journal(id),
        action_id UUID NOT NULL REFERENCES journey_actions(id),created_by TEXT NOT NULL REFERENCES users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(entry_id,action_id))''')
    op.execute('''CREATE TABLE IF NOT EXISTS business_work_digest_settings (
        business_id TEXT PRIMARY KEY REFERENCES businesses(id),local_time TIME NOT NULL DEFAULT '18:00',enabled BOOLEAN NOT NULL DEFAULT TRUE)''')
    # Preserve all previously allowed task flows while admitting journal tasks.
    op.execute("""DO $$ DECLARE previous TEXT; BEGIN
        SELECT pg_get_expr(conbin,conrelid) INTO previous FROM pg_constraint
        WHERE conrelid='journey_actions'::regclass AND conname='ck_journey_actions_flow';
        IF previous IS NULL THEN RAISE EXCEPTION 'Missing journey flow constraint'; END IF;
        ALTER TABLE journey_actions DROP CONSTRAINT ck_journey_actions_flow;
        EXECUTE 'ALTER TABLE journey_actions ADD CONSTRAINT ck_journey_actions_flow CHECK ((' || previous || ') OR flow_type = ''work_journal'')';
    END $$""")
    op.execute("CREATE INDEX IF NOT EXISTS work_journal_review_queue ON business_work_journal(business_id,review_status,created_at)")


def downgrade():
    # Feature rollback preserves observations, decisions and linked tasks.
    pass
