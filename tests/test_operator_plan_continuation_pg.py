"""Isolated PostgreSQL schema; no production or external generation calls."""
import os
import uuid
from types import SimpleNamespace
from datetime import date
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from services import content_plan_service


@pytest.fixture
def database(monkeypatch):
    dsn=os.getenv('OPERATOR_VOICE_TEST_DSN')
    if not dsn: pytest.skip('disposable PostgreSQL DSN required')
    conn=psycopg2.connect(dsn,cursor_factory=RealDictCursor)
    schema='plan_'+uuid.uuid4().hex
    c=conn.cursor();c.execute('CREATE SCHEMA '+schema);c.execute('SET search_path TO '+schema)
    c.execute('''CREATE TABLE contentplans (id text PRIMARY KEY,business_id text,network_id text,scope_type text,scope_target_id text,title text,
        period_days int,period_start date,period_end date,plan_status text,generation_mode text,input_snapshot_json jsonb,generated_plan_json jsonb,
        published_plan_json jsonb,created_by text,created_at timestamptz DEFAULT clock_timestamp())''')
    c.execute('''CREATE TABLE contentplanitems (id text PRIMARY KEY,plan_id text,business_id text,scheduled_for date,content_type text,theme text,goal text,
        source_kind text,source_ref text,seo_keyword text,service_id text,transaction_id text,seo_views int,location_scope text,status text,metadata_json jsonb)''')
    c.execute("INSERT INTO contentplans(id,business_id,period_end,created_by,generated_plan_json) VALUES ('old','b','2026-09-05','u','{\"selected_channels\":[\"google_business\"]}')")
    c.execute("INSERT INTO contentplanitems(id,plan_id,business_id,scheduled_for,theme,status) VALUES ('old-item','old','b','2026-09-12','Подсветить услугу: Трансфер','edited')")
    c.execute("INSERT INTO contentplans(id,business_id,period_end,created_by) VALUES ('foreign','foreign-business','2030-01-01','v')")
    conn.commit()
    monkeypatch.setattr(content_plan_service,'DatabaseManager',lambda:SimpleNamespace(conn=conn,close=lambda:None))
    monkeypatch.setattr(content_plan_service,'ensure_content_plan_tables',lambda _:None)
    monkeypatch.setattr(content_plan_service,'get_allowed_content_plan_horizons',lambda _:[30])
    monkeypatch.setattr(content_plan_service,'load_plan_context_for_business',lambda *args:{'subscription':{'maps_content_access':True},'business':{'id':'b','name':'Riderra'},'services':[{'name':'Трансфер'}]})
    monkeypatch.setattr(content_plan_service,'_record_content_plan_event',lambda **kwargs:None)
    def get_plan(user,plan_id):
        cur=conn.cursor();cur.execute('SELECT * FROM contentplans WHERE id=%s',(plan_id,));return dict(cur.fetchone())
    monkeypatch.setattr(content_plan_service,'get_content_plan',get_plan)
    yield conn
    conn.rollback();c.execute('DROP SCHEMA '+schema+' CASCADE');conn.commit();conn.close()


def test_creation_preserves_previous_plan_and_crash_retry_returns_same_plan(database):
    kwargs={'scope_type':'single_location','scope_target_id':'b','period_days':30,'density':'standard','content_mix':{},
        'continuation_message':'12 го заканчивается контент план, сделай следующий, старый не удаляй','operator_request_id':'voice:one'}
    first=content_plan_service.create_generated_content_plan('u','b',**kwargs)
    repeated=content_plan_service.create_generated_content_plan('u','b',**kwargs)
    assert first['id']==repeated['id']
    assert first['period_start']==date(2026,9,13)
    assert first['period_end']==date(2026,10,12)
    assert first['generated_plan_json']['meta']['previous_plan_id']=='old'
    assert first['generated_plan_json']['selected_channels']==['google_business']
    c=database.cursor();c.execute("SELECT COUNT(*) n FROM contentplans WHERE business_id='b'");assert c.fetchone()['n']==2
    c.execute("SELECT status,scheduled_for FROM contentplanitems WHERE id='old-item'");assert dict(c.fetchone())=={'status':'edited','scheduled_for':date(2026,9,12)}
    c.execute('SELECT theme,scheduled_for FROM contentplanitems WHERE plan_id=%s',(first['id'],));items=c.fetchall()
    assert items and all(item['theme']!='Подсветить услугу: Трансфер' for item in items)
    assert all(date(2026,9,13)<=item['scheduled_for']<=date(2026,10,12) for item in items)
