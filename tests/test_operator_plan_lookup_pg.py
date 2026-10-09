"""Regression: a newer archived test plan must not hide the working calendar."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from services import operator_editorial, operator_mobile_modules


@pytest.fixture
def plans(monkeypatch):
    dsn = os.environ.get('OPERATOR_PLAN_LOOKUP_TEST_DSN')
    if not dsn:
        pytest.skip('isolated PostgreSQL DSN not configured')
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    conn.set_client_encoding('UTF8')
    schema = 'plan_lookup_' + uuid.uuid4().hex
    c = conn.cursor()
    c.execute('CREATE SCHEMA ' + schema)
    c.execute('SET search_path TO ' + schema)
    c.execute('CREATE TABLE businesses(id TEXT PRIMARY KEY,name TEXT)')
    c.execute('''CREATE TABLE contentplans(id TEXT PRIMARY KEY,business_id TEXT,title TEXT,
        period_start DATE,period_end DATE,period_days INT,plan_status TEXT,
        created_at TIMESTAMP,updated_at TIMESTAMP)''')
    c.execute('''CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,business_id TEXT,
        theme TEXT,goal TEXT,scheduled_for DATE,status TEXT,draft_text TEXT,usernews_id TEXT,
        metadata_json JSONB,updated_at TIMESTAMP,content_type TEXT,source_kind TEXT,
        source_ref TEXT,seo_keyword TEXT,service_id TEXT,transaction_id TEXT)''')
    c.execute("CREATE TABLE content_voice_profiles(business_id TEXT,preferences_json JSONB)")
    c.execute("INSERT INTO businesses VALUES ('b','Client'),('foreign','Other client')")
    c.execute("""INSERT INTO contentplans(id,business_id,title,plan_status,created_at) VALUES
        ('working','b','Working calendar','generated','2026-09-14'),
        ('other-active','b','Second active calendar','generated','2026-09-15'),
        ('test','b','DO NOT PUBLISH','archived','2026-10-08'),
        ('foreign-plan','foreign','Other client','generated','2026-10-09')""")
    c.execute("""INSERT INTO contentplanitems(id,plan_id,business_id,theme,scheduled_for,status) VALUES
        ('real','working','b','Colour strands','2026-10-09','draft_generated'),
        ('second','other-active','b','Second topic','2026-10-10','planned'),
        ('test-item','test','b','Test delivery','2026-10-09','approved'),
        ('foreign-item','foreign-plan','foreign','Private topic','2026-10-09','planned')""")
    monkeypatch.setattr(operator_mobile_modules, '_table_exists', lambda *_: True)
    def authorize(_cursor, user_id, business_id):
        if user_id != 'u' or business_id != 'b':
            raise PermissionError('denied')
    monkeypatch.setattr(operator_editorial, 'authorize_actor', authorize)
    try:
        yield c
    finally:
        conn.rollback()
        conn.close()


def test_editorial_context_includes_all_active_plans(plans):
    result = operator_editorial.read_context(plans, 'b', 'u', {})
    assert {item['id'] for item in result['items']} == {'real', 'second'}


def test_exact_item_lookup_is_not_restricted_to_newest_plan(plans):
    assert [row['id'] for row in operator_editorial._items(plans, 'b', item_id='real', lock=True)] == ['real']


def test_explicit_plan_stays_scoped_and_archive_is_readable(plans):
    assert [row['id'] for row in operator_editorial._items(plans, 'b', plan_id='working')] == ['real']
    assert [row['id'] for row in operator_editorial._items(plans, 'b', plan_id='test')] == ['test-item']
    assert operator_editorial._items(plans, 'b', item_id='foreign-item') == []


def test_menu_query_source_includes_active_calendars_not_archived_test(plans):
    items = operator_mobile_modules._content(plans, {'kind':'business','business_ids':['b']})
    assert {item['id'] for item in items} == {'real', 'second'}


def test_foreign_context_remains_denied(plans):
    with pytest.raises(PermissionError):
        operator_editorial.read_context(plans, 'foreign', 'u', {})
