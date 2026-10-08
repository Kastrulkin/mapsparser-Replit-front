from datetime import date
from flask import Flask
import pytest
from tests.test_outreach_continuation_pg import db
from api import operator_api


@pytest.mark.parametrize('platform,admin,expected', [(True,True,{'b','b2'}),(False,False,{'b'}),(True,False,set())])
@pytest.mark.parametrize('legacy_timezone', [True, False])
def test_today_query_respects_resolved_scope_and_local_dates(db, monkeypatch, platform, admin, expected, legacy_timezone):
    conn, cursor = db
    cursor.execute("ALTER TABLE businesses ADD COLUMN name TEXT,ADD COLUMN address TEXT,ADD COLUMN entity_group TEXT DEFAULT 'client'")
    cursor.execute("UPDATE businesses SET name=id,address=id")
    cursor.execute('CREATE TABLE business_finance_settings(business_id TEXT PRIMARY KEY,timezone TEXT)')
    cursor.execute("INSERT INTO business_finance_settings VALUES ('b','Europe/Moscow'),('b2','America/Los_Angeles')")
    if legacy_timezone:
        cursor.execute('ALTER TABLE businesses ADD COLUMN timezone TEXT')
        cursor.execute("UPDATE businesses SET timezone='UTC'")
    cursor.execute('CREATE TABLE contentplans(id TEXT PRIMARY KEY,plan_status TEXT)')
    cursor.execute('CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,business_id TEXT,status TEXT,theme TEXT,scheduled_for TIMESTAMPTZ)')
    cursor.execute('CREATE TABLE social_posts(id TEXT PRIMARY KEY,business_id TEXT,content_plan_item_id TEXT,platform TEXT,status TEXT,publish_mode TEXT,scheduled_for TIMESTAMPTZ,platform_text TEXT,provider_post_url TEXT,metadata_json JSONB)')
    cursor.execute("INSERT INTO social_posts VALUES('p','b',NULL,'telegram','needs_review','manual','2026-10-08 00:00+03','Copy',NULL,'{}')")
    cursor.execute("INSERT INTO social_posts VALUES('p2','b2',NULL,'vk','needs_review','manual','2026-10-08 00:00-07','Copy',NULL,'{}')")
    class Database:
        def __init__(self): self.conn=conn
        def close(self): pass
    monkeypatch.setattr(operator_api,'DatabaseManager',Database)
    monkeypatch.setattr(operator_api,'require_auth_from_request',lambda:{'user_id':'u','is_superadmin':admin})
    # The authenticated scope resolver is tested separately; this verifies real
    # PostgreSQL query scoping and per-location date filtering after resolution.
    monkeypatch.setattr(operator_api,'_resolve_operator_read_scope',lambda *args:{'kind':'platform' if platform else 'business','business_ids':['b']})
    app=Flask(__name__); app.register_blueprint(operator_api.operator_bp)
    response=app.test_client().get('/api/operator/content/today?from_date=2026-10-08&to_date=2026-10-08')
    if platform and not admin:
        assert response.status_code==403
        return
    assert response.status_code==200
    rows=response.get_json()['businesses']
    assert {row['id'] for row in rows}==expected
    assert all(row['posts'][0]['local_date']=='2026-10-08' for row in rows)
    assert all(row['posts'][0]['status']=='needs_review' for row in rows)
