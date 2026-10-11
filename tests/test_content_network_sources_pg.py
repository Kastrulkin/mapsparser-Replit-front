import sys
from types import SimpleNamespace
from tests.test_outreach_continuation_pg import db
from services.content_network_renewal import refresh_sources
from services.operator_async_jobs import create_operator_async_job


def test_unavailable_sources_are_cached_with_dates_not_reported_fresh(db,monkeypatch):
    conn,cursor=db
    cursor.execute('CREATE TABLE externalbusinessreviews(business_id TEXT,updated_at TIMESTAMPTZ)')
    cursor.execute("INSERT INTO externalbusinessreviews VALUES ('b','2026-10-01')")
    cursor.execute('CREATE TABLE wordstatkeywordscustom(business_id TEXT,updated_at TIMESTAMPTZ)')
    cursor.execute("INSERT INTO wordstatkeywordscustom VALUES ('b','2026-09-15')")
    cursor.execute('CREATE TABLE userservices(id TEXT,business_id TEXT,name TEXT,price TEXT,updated_at TIMESTAMPTZ,is_active BOOLEAN)')
    cursor.execute("INSERT INTO userservices VALUES ('service','b','Стрижка','500',NOW(),TRUE)")
    cursor.execute('CREATE TABLE contentplans(id TEXT,business_id TEXT,input_snapshot_json JSONB)')
    cursor.execute("INSERT INTO contentplans VALUES ('previous','b','{}')")
    def unavailable(*args):
        raise ValueError('provider_unavailable')
    monkeypatch.setitem(sys.modules,'api.wordstat_api',SimpleNamespace(_refresh_business_wordstat_keywords=unavailable))
    monkeypatch.setitem(sys.modules,'services.operator_fresh_reviews',SimpleNamespace(refresh_reviews_from_operator=lambda *a,**kw: {'status':'blocked','blocked_reasons':['provider_unavailable']}))
    job=create_operator_async_job(cursor,user_id='u',action_id=None,business_id='b',kind='content_plan_network_renewal',
        payload={'previous_plan_id':'previous'},idempotency_key='renew',stage='refresh')
    cursor.execute('SELECT * FROM operator_async_jobs WHERE id=%s',(job['id'],))
    job=cursor.fetchone()
    sources,pending=refresh_sources(conn,job)
    assert not pending
    assert sources['keywords']['state']=='cached' and sources['reviews']['state']=='cached'
    assert sources['keywords']['cached_snapshot']['latest_seen_at'].date().isoformat()=='2026-09-15'
    assert sources['reviews']['cached_snapshot']['latest_seen_at'].date().isoformat()=='2026-10-01'
    assert sources['services']['rows'][0]['price']=='500'
