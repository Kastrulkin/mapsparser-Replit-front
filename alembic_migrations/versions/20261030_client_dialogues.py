"""Durable client conversations, staff handoffs and message history."""
from alembic import op

revision = '20261030_client_dialogues'
down_revision = '20261028_trello_read_only'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE IF NOT EXISTS aiagentconversations (
        id TEXT PRIMARY KEY,
        business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
        client_phone TEXT NOT NULL,
        client_name TEXT,
        current_state TEXT NOT NULL DEFAULT 'greeting',
        conversation_history TEXT NOT NULL DEFAULT '[]',
        is_agent_paused INTEGER NOT NULL DEFAULT 0 CHECK (is_agent_paused IN (0,1)),
        last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(business_id, client_phone)
    )''')
    op.execute('''CREATE TABLE IF NOT EXISTS aiagentmessages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES aiagentconversations(id) ON DELETE CASCADE,
        message_type TEXT NOT NULL DEFAULT 'text',
        content TEXT NOT NULL,
        sender TEXT NOT NULL CHECK (sender IN ('client','agent','operator')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )''')
    op.execute('CREATE INDEX IF NOT EXISTS ix_client_dialogue_queue ON aiagentconversations(business_id,current_state,last_message_at DESC)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_client_dialogue_messages ON aiagentmessages(conversation_id,created_at)')


def downgrade():
    # Keep client history on application rollback. No implicit production data deletion.
    pass
