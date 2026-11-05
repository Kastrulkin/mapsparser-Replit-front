"""Scope client personas to their business; retain unassigned legacy templates."""
import json
from alembic import op
from sqlalchemy import text

revision = '20261030_client_agent_scope'
down_revision = '20261030_client_dialogues'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS business_id TEXT REFERENCES businesses(id)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_aiagents_business_id ON aiagents(business_id)')
    connection = op.get_bind()
    bindings = {}
    for row in connection.execute(text("SELECT id, to_jsonb(b)->>'ai_agents_config' config, to_jsonb(b)->>'ai_agent_id' legacy FROM businesses b")).mappings():
        try:
            config = json.loads(row['config'] or '{}')
        except (ValueError, TypeError):
            config = {}
        ids = {item.get('agent_id') for item in config.values() if isinstance(item, dict)} if isinstance(config, dict) else set()
        ids.add(row['legacy'])
        for agent_id in ids:
            if agent_id and agent_id not in ('booking_agent_default', 'marketing_agent_default'):
                bindings.setdefault(str(agent_id), set()).add(row['id'])
    # Ambiguous/shared legacy records remain unassigned; never guess ownership.
    for agent_id, businesses in bindings.items():
        if len(businesses) == 1:
            connection.execute(text('UPDATE aiagents SET business_id=:business WHERE id=:agent AND business_id IS NULL'), {'business': next(iter(businesses)), 'agent': agent_id})


def downgrade():
    op.execute('DROP INDEX IF EXISTS ix_aiagents_business_id')
    op.execute('ALTER TABLE aiagents DROP COLUMN IF EXISTS business_id')
