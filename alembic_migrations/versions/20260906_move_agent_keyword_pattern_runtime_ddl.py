"""Move remaining agent, keyword and industry-pattern runtime DDL into Alembic.

Revision ID: 20260906_009
Revises: 20260906_008
"""

from alembic import op


revision = "20260906_009"
down_revision = "20260906_008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE IF NOT EXISTS aiagents (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL, description TEXT,
        personality TEXT, states_json TEXT, workflow TEXT, task TEXT, identity TEXT,
        speech_style TEXT, restrictions_json TEXT, variables_json TEXT,
        is_active INTEGER DEFAULT 1, created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    for statement in (
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS description TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS personality TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS states_json TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS workflow TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS task TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS identity TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS speech_style TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS restrictions_json TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS variables_json TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS created_by TEXT",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE aiagents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    ):
        op.execute(statement)
    op.execute("""INSERT INTO aiagents (id,name,type,description,personality,is_active)
        VALUES ('booking_agent_default','Booking Agent','booking','Агент для записи клиентов','Вежливый, пунктуальный администратор. Твоя задача - записать клиента на услугу.',1)
        ON CONFLICT (id) DO NOTHING""")

    op.execute("""CREATE TABLE IF NOT EXISTS wordstatkeywords (
        id TEXT PRIMARY KEY, keyword TEXT UNIQUE NOT NULL, views INTEGER DEFAULT 0,
        category TEXT DEFAULT 'other', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_views ON wordstatkeywords(views DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_category ON wordstatkeywords(category)")
    op.execute("""CREATE TABLE IF NOT EXISTS wordstatkeywordsexcluded (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL, keyword TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE (business_id, keyword)
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_excluded_business ON wordstatkeywordsexcluded(business_id)")
    op.execute("""CREATE TABLE IF NOT EXISTS wordstatkeywordscustom (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL, keyword TEXT NOT NULL,
        views INTEGER DEFAULT 0, category TEXT DEFAULT 'custom',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (business_id, keyword)
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_custom_business ON wordstatkeywordscustom(business_id)")
    op.execute("""CREATE TABLE IF NOT EXISTS seonegativekeywords (
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL, phrase TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT 'global', category TEXT DEFAULT '', is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (business_id, phrase, scope, category)
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_seo_negative_business ON seonegativekeywords(business_id)")

    op.execute("""CREATE TABLE IF NOT EXISTS industry_pattern_impact_events (
        id TEXT PRIMARY KEY, version_id TEXT NOT NULL, industry_key TEXT NOT NULL,
        pattern_type TEXT NOT NULL, business_id TEXT, user_id TEXT, source TEXT NOT NULL,
        event_type TEXT NOT NULL, result_status TEXT, metrics_json JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    op.execute("""CREATE TABLE IF NOT EXISTS industry_pattern_admin_events (
        id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL, target_type TEXT,
        target_id TEXT, metadata_json JSONB, created_at TIMESTAMPTZ DEFAULT NOW()
    )""")


def downgrade():
    # Agents, keyword choices, and pattern evidence survive code rollback.
    pass
