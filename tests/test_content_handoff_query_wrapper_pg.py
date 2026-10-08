from database_manager import DBConnectionWrapper
from services.content_publish_notifications import collect_due_content_publish_handoffs
from tests.test_outreach_continuation_pg import db


def test_collector_works_through_production_query_wrapper(db):
    conn, cursor = db
    cursor.execute('ALTER TABLE businesses ADD COLUMN name TEXT, ADD COLUMN address TEXT, ADD COLUMN timezone TEXT')
    cursor.execute('CREATE TABLE business_finance_settings(business_id TEXT,timezone TEXT)')
    cursor.execute('''CREATE TABLE social_posts(id TEXT,business_id TEXT,platform TEXT,
        publish_mode TEXT,status TEXT,scheduled_for TIMESTAMPTZ,metadata_json JSONB,
        created_at TIMESTAMPTZ)''')
    scope = {'business_id':'business','user_id':'owner','telegram_id':'123',
             'required_platforms':['telegram','vk','max'],'lead_days':1,'time':'10:00'}
    assert collect_due_content_publish_handoffs(DBConnectionWrapper(conn),
                                               compiled_scope=scope) == []
