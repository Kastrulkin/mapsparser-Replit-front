"""Real PostgreSQL scope regression; disposable local CI database only."""
import os
import pytest
from services import operator_editorial
from tests.helpers.postgres_safety import IsolatedTestSchema


def test_all_plan_items_include_missing_channels_and_preserve_explicit_scope(monkeypatch):
    dsn = os.environ.get('OPERATOR_VOICE_TEST_DSN')
    if not dsn:
        pytest.skip('disposable PostgreSQL required')
    scope = IsolatedTestSchema(dsn, 'plan_')
    try:
        c = scope.first.cursor()
        c.execute('''CREATE TABLE contentplans(id TEXT PRIMARY KEY,business_id TEXT,title TEXT,
            period_start DATE,period_end DATE,plan_status TEXT,created_at TIMESTAMPTZ DEFAULT NOW())''')
        c.execute('''CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,business_id TEXT,
            theme TEXT,goal TEXT,scheduled_for DATE,status TEXT,draft_text TEXT,usernews_id TEXT,
            metadata_json JSONB,updated_at TIMESTAMPTZ,content_type TEXT,source_kind TEXT,
            source_ref TEXT,seo_keyword TEXT,service_id TEXT,transaction_id TEXT)''')
        c.execute('CREATE TABLE social_posts(id TEXT, business_id TEXT,content_plan_item_id TEXT,platform TEXT,status TEXT,platform_text TEXT,base_text TEXT,media_json JSONB)')
        c.execute('CREATE TABLE businesses(id TEXT,network_id TEXT)')
        c.execute("INSERT INTO businesses VALUES('b',NULL),('other',NULL)")
        c.execute('CREATE TABLE photo_assets(id TEXT,business_id TEXT,metadata_json JSONB,category TEXT)')
        c.execute('''CREATE TABLE photo_asset_usage_events(id TEXT,business_id TEXT,target_id TEXT,
            photo_asset_id TEXT,usage_type TEXT,target_platform TEXT,created_at TIMESTAMPTZ DEFAULT NOW())''')
        c.execute('CREATE TABLE content_voice_profiles(business_id TEXT,preferences_json JSONB)')
        for plan, business, status in [('old','b','generated'), ('new','b','generated'), ('archive','b','archived'), ('foreign','other','generated')]:
            c.execute('INSERT INTO contentplans(id,business_id,title,plan_status) VALUES(%s,%s,%s,%s)', (plan,business,plan,status))
            c.execute("INSERT INTO contentplanitems(id,plan_id,business_id,theme,scheduled_for) VALUES(%s,%s,%s,%s,'2026-10-15')", (plan+'-item',plan,business,plan))
        c.execute("INSERT INTO social_posts VALUES('s','b','new-item','google_business','needs_review','Готовый текст',NULL,'[{}]')")
        c.execute("INSERT INTO photo_assets VALUES('photo','b','{}','process'),('private','other','{}','process')")
        c.execute("INSERT INTO photo_asset_usage_events VALUES('usage','b','new-item','photo','publication',NULL,NOW())")
        c.execute("INSERT INTO photo_asset_usage_events VALUES('wrong-scope','b','old-item','private','publication',NULL,NOW())")
        c.execute("UPDATE contentplanitems SET draft_text='Текст' WHERE id='new-item'")
        monkeypatch.setattr(operator_editorial, 'authorize_actor', lambda *_args: None)
        result = operator_editorial.read_context(c,'b','u',{})
        items = {item['id']: item for item in result['items']}
        assert set(items) == {'old-item','new-item'}
        assert items['old-item']['channel_versions'] == []
        assert items['new-item']['channel_versions'] == [{'platform':'google_business','status':'needs_review','has_text':True,'has_media':True}]
        assert items['new-item']['selected_photo_asset_id'] == 'photo'
        assert items['new-item']['has_text'] is True
        assert items['old-item']['has_text'] is False
        assert items['old-item']['selected_photo_asset_id'] == ''
        assert result['search_scope'] == 'all_nonarchived_plans'
        selected = operator_editorial.read_context(c,'b','u',{'plan_id':'new'})
        assert [item['id'] for item in selected['items']] == ['new-item']
        assert selected['search_scope'] == 'selected_plan'
        assert operator_editorial.read_context(c,'b','u',{'plan_id':'foreign'})['items'] == []
        c.execute('SELECT COUNT(*) n FROM social_posts')
        assert c.fetchone()['n'] == 1
    finally:
        scope.close()
