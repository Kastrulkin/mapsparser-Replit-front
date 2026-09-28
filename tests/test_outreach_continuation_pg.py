"""Disposable local PostgreSQL. No provider calls or production data."""
import importlib.util
import os
import uuid
from pathlib import Path
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, Json
import pytest
from services import outreach_continuation
from services import operator_async_jobs


@pytest.fixture
def db(monkeypatch):
    dsn = os.environ.get('OUTREACH_TEST_DSN')
    if not dsn:
        pytest.skip('OUTREACH_TEST_DSN required; disposable PostgreSQL only')
    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    conn.set_client_encoding("UTF8")
    schema = 'outreach_test_' + uuid.uuid4().hex
    cur = conn.cursor()
    cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
    cur.execute('CREATE TABLE users(id TEXT PRIMARY KEY, is_active BOOLEAN DEFAULT TRUE, is_superadmin BOOLEAN DEFAULT FALSE)')
    cur.execute('CREATE TABLE businesses(id TEXT PRIMARY KEY, owner_id TEXT, network_id TEXT, is_active BOOLEAN DEFAULT TRUE)')
    cur.execute('CREATE TABLE networks(id TEXT PRIMARY KEY,owner_id TEXT)')
    cur.execute('CREATE TABLE business_members(business_id TEXT,user_id TEXT,role TEXT,status TEXT)')
    cur.execute('CREATE TABLE network_members(network_id TEXT,user_id TEXT,role TEXT,status TEXT)')
    cur.execute('CREATE TABLE operatoractions(id TEXT PRIMARY KEY)')
    cur.execute("INSERT INTO users(id) VALUES ('u'),('u2')")
    cur.execute("INSERT INTO businesses(id,owner_id) VALUES ('b','u'),('b2','u2')")
    from alembic import op
    monkeypatch.setattr(op,'execute',cur.execute)
    path = Path(__file__).parents[1]/'alembic_migrations/versions/20260727_add_operator_async_jobs.py'
    spec = importlib.util.spec_from_file_location('outreach_test_migration',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    cur.execute('ALTER TABLE operator_async_jobs ADD COLUMN lease_token TEXT')
    conn.commit()
    try:
        yield conn,cur
    finally:
        conn.rollback()
        cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        conn.commit();conn.close()


def config():
    return {'audience':'Agencies','offer':'Transfers','queries':[{'query':'agency','city':'Delhi'},{'query':'travel','city':'Mumbai'}]}


def test_draft_dedup_start_and_new_run(db):
    conn,cur=db
    first=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config(),request_id='r1')
    same=outreach_continuation.create_task(cur,business_id='b',user_id='u2',config=config(),request_id='r2')
    assert same['id']==first['id']
    assert first['status']=='waiting_for_review'
    assert operator_async_jobs.claim_next_operator_async_job(cur) is None
    with pytest.raises(ValueError,match='stale_review'):
        outreach_continuation.control_task(cur,task_id=first['id'],business_id='b',user_id='u',action='start',revision='old')
    started=outreach_continuation.control_task(cur,task_id=first['id'],business_id='b',user_id='u',action='start',revision=first['revision'])
    assert started['status']=='queued'
    outreach_continuation.control_task(cur,task_id=first['id'],business_id='b',user_id='u',action='stop',revision=first['revision'])
    again=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config(),request_id='r3')
    assert again['id']!=first['id']
    assert outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config(),request_id='r3')['id']==again['id']


def test_pause_fences_old_lease_and_uncertain_search(db):
    conn,cur=db
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())
    outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='start',revision=task['revision'])
    claimed=operator_async_jobs.claim_next_operator_async_job(cur)
    cur.execute("UPDATE operator_async_jobs SET result_json=result_json || %s WHERE id=%s", (Json({'inflight_search':True,'search_calls':1}),task['id']))
    paused=outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='pause',revision=task['revision'])
    assert paused['state']['blocker']=='search_result_uncertain'
    assert outreach_continuation._lock_current(cur,claimed) is None
    assert not outreach_continuation._save(cur,claimed,{},stage='stale result')
    with pytest.raises(ValueError,match='search_result_uncertain'):
        outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='resume',revision=task['revision'])
    resolved=outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='acknowledge_search',revision=task['revision'])
    assert resolved['state']['search_calls']==1
    assert not resolved['state']['inflight_search']
    resumed=outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='resume',revision=task['revision'])
    assert resumed['status']=='queued'


def test_crash_preserves_reservation_and_business_isolation(db):
    conn,cur=db
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())
    outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='start',revision=task['revision'])
    claimed=operator_async_jobs.claim_next_operator_async_job(cur)
    cur.execute("UPDATE operator_async_jobs SET result_json=result_json || %s, heartbeat_at=NOW()-INTERVAL '1 hour' WHERE id=%s",(Json({'inflight_search':True,'search_calls':1}), task['id']))
    conn.commit()
    assert operator_async_jobs.recover_stale_operator_async_jobs(cur)==1
    conn.commit()
    assert outreach_continuation._lock_current(cur,claimed) is None
    assert outreach_continuation.list_tasks(cur,business_id='b2',user_id='u')==[]
    current=outreach_continuation.list_tasks(cur,business_id='b',user_id='u')[0]
    assert current['state']['inflight_search']
    assert current['state']['search_calls']==1


def test_actual_write_roles_and_disabled_actor(db):
    _,cur=db
    cur.execute("INSERT INTO business_members VALUES ('b','u2','viewer','active')")
    assert not outreach_continuation.actor_can_write(cur,'b',{'user_id':'u2','is_active':True})
    assert outreach_continuation.actor_can_write(cur,'b',{'user_id':'u','is_active':True})
    assert not outreach_continuation.actor_can_write(cur,'b',{'user_id':'u','is_active':False})
    assert not outreach_continuation.actor_can_write(cur,'b',{'user_id':'u','is_active':True,'session_kind':'demo'})
    cur.execute("UPDATE business_members SET role='manager' WHERE user_id='u2'")
    assert outreach_continuation.actor_can_write(cur,'b',{'user_id':'u2','is_active':True})
    cur.execute("UPDATE business_members SET status='revoked' WHERE user_id='u2'")
    assert not outreach_continuation.actor_can_write(cur,'b',{'user_id':'u2','is_active':True})


def test_recovery_keeps_budgets_and_terminal_chat_rerun(db):
    _,cur=db
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())
    cur.execute("UPDATE operator_async_jobs SET result_json=result_json || %s WHERE id=%s", (Json({'llm_calls':2,'draft_attempts':1,'qualifications':{'w':{'status':'checking'}},'campaign_results':{'w2':{'status':'preparing'}}}),task['id']))
    reset=outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='retry_failed',revision=task['revision'])
    assert reset['state']['llm_calls']==2 and reset['state']['draft_attempts']==1
    assert reset['state']['qualifications']=={} and reset['state']['campaign_results']=={}
    outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='stop',revision=task['revision'])
    assert outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())['id']!=task['id']


@pytest.fixture
def execution(db, monkeypatch):
    conn,cur=db
    class Connection:
        def cursor(self,*args,**kwargs): return conn.cursor(*args,**kwargs)
        def commit(self): conn.commit()
        def rollback(self): conn.rollback()
        def close(self): pass
    import pg_db_utils
    from services import partnership_leads_service
    monkeypatch.setattr(pg_db_utils,'get_db_connection',lambda:Connection())
    monkeypatch.setattr(partnership_leads_service,'get_capability_access',lambda *a,**k:{'allowed':True})
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED','true')
    monkeypatch.setenv('OUTREACH_CONTINUATION_BUSINESS_IDS','b')
    monkeypatch.setenv('OUTREACH_DEEPSEEK_DRAFTING_ENABLED','true')
    monkeypatch.setenv('OUTREACH_DEEPSEEK_BUSINESS_IDS','b')
    monkeypatch.setenv('LLM_ROUTER_ENABLED','true')
    monkeypatch.setenv('LLM_DEEPSEEK_BUSINESS_IDS','b')
    monkeypatch.setenv('DEEPSEEK_API_KEY','disposable-test-no-provider-calls')
    cur.execute('CREATE TABLE prospectingleads(id TEXT PRIMARY KEY, business_id TEXT, website TEXT, search_payload_json JSONB)')
    cur.execute('CREATE TABLE lead_workstreams(id TEXT PRIMARY KEY,lead_id TEXT,client_business_id TEXT,status TEXT)')
    cur.execute('CREATE TABLE lead_workstream_research(id TEXT PRIMARY KEY,workstream_id TEXT,evidence_json JSONB,signals_json JSONB,message_readiness_json JSONB,researched_at TIMESTAMPTZ DEFAULT NOW())')
    cur.execute('CREATE TABLE lead_enrichment_jobs(id TEXT,workstream_id TEXT,status TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')
    cur.execute('CREATE TABLE outreach_campaigns(id TEXT PRIMARY KEY,workstream_id TEXT,status TEXT,created_at TIMESTAMPTZ DEFAULT NOW())')
    conn.commit()
    def tick():
        cur.execute("UPDATE operator_async_jobs SET next_attempt_at=NOW() WHERE status='queued'")
        row=operator_async_jobs.claim_next_operator_async_job(cur)
        conn.commit()
        assert row
        return outreach_continuation.process_job(row)
    return conn,cur,tick


def test_worker_search_qualify_draft_and_no_dispatch(execution,monkeypatch):
    conn,cur,tick=execution
    from api.prospecting import partner_discovery
    from services import outreach_public_evidence, outreach_campaign_service
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config={**config(),'queries':[config()['queries'][0]]})
    outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='start',revision=task['revision'])
    monkeypatch.setattr(outreach_continuation,'_start_search',lambda *a:{'id':'run1','dataset_id':'ds'})
    monkeypatch.setattr(outreach_continuation,'_poll_search',lambda *a:[{'name':'Agency','source_url':'https://maps.example/a','website':'https://agency.example'}])
    def insert(cursor,**kwargs):
        cursor.execute("INSERT INTO prospectingleads VALUES ('lead','b','https://agency.example',%s)",(Json(kwargs['search_payload']),))
        cursor.execute("INSERT INTO lead_workstreams VALUES ('ws','lead','b','new')")
        cursor.execute("INSERT INTO lead_workstream_research(id,workstream_id,signals_json) VALUES ('research','ws','[]')")
        cursor.execute("INSERT INTO lead_enrichment_jobs(id,workstream_id,status) VALUES ('e','ws','completed')")
        return 'lead',True
    monkeypatch.setattr(partner_discovery,'_insert_partnership_lead_if_new',insert)
    monkeypatch.setattr(partner_discovery,'_ensure_imported_partnership_workstream',lambda *a,**k:'ws')
    evidence=[{'id':'fact','fact':'We sell Phuket holidays','source_url':'https://agency.example/phuket','source_type':'public_website'}]
    monkeypatch.setattr(outreach_public_evidence,'collect_candidate_evidence',lambda *a:evidence)
    monkeypatch.setattr(outreach_continuation,'qualify_audience',lambda *a,**k:{'status':'qualified','evidence':evidence[0]})
    monkeypatch.setattr(outreach_campaign_service,'build_preview',lambda *a,**k:{'status':'ready','touches':[{'text':'draft'}]})
    def persist(cursor,preview,**kwargs):
        cursor.execute("INSERT INTO outreach_campaigns(id,workstream_id,status) VALUES ('campaign','ws','draft')")
        return {'id':'campaign'}
    monkeypatch.setattr(outreach_campaign_service,'persist_preview',persist)
    for _ in range(5):
        assert tick()['status']=='progress_saved'
    current=outreach_continuation.list_tasks(cur,business_id='b',user_id='u')[0]
    assert current['status']=='waiting_for_review'
    assert current['state']['campaign_results']['ws']['campaign_id']=='campaign'
    assert current['state']['search_calls']==1 and current['state']['llm_calls']==1
    assert current['external_dispatch_performed'] is False
    cur.execute("SELECT signals_json FROM lead_workstream_research WHERE id='research'")
    assert cur.fetchone()['signals_json'][0]['fact']=='We sell Phuket holidays'
    cur.execute('SELECT COUNT(*) n FROM outreach_campaigns')
    assert cur.fetchone()['n']==1


def test_poll_timeout_is_finite_and_does_not_restart_search(execution,monkeypatch):
    _,cur,tick=execution
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())
    outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='start',revision=task['revision'])
    cur.execute('UPDATE operator_async_jobs SET result_json=result_json || %s WHERE id=%s',(Json({'phase':'search_poll','search_polls':20,'search_calls':1,'search_run':{'id':'r'}}),task['id']))
    monkeypatch.setattr(outreach_continuation,'_poll_search',lambda *a:pytest.fail('No unbounded poll'))
    assert tick()['status']=='pending_human'
    task=outreach_continuation.list_tasks(cur,business_id='b',user_id='u')[0]
    assert task['state']['blocker']=='search_poll_timeout' and task['state']['search_calls']==1


def test_api_create_read_start_and_viewer_denial(execution,monkeypatch):
    _,cur,_=execution
    from flask import Flask
    from api import partnership_leads_api
    from api.prospecting import access_schema
    from services import partnership_leads_service
    monkeypatch.setattr(access_schema,'_require_auth',lambda:({'user_id':'u','is_active':True},None))
    monkeypatch.setattr(access_schema,'_resolve_business_for_user',lambda cursor,user,requested:requested)
    monkeypatch.setattr(partnership_leads_service,'_partnership_write_access',lambda *args:None)
    app=Flask(__name__)
    app.register_blueprint(partnership_leads_api.partnership_leads_bp)
    client=app.test_client()
    response=client.post('/api/partnership/continuations',json={'business_id':'b','config':config(),'request_id':'http-one'})
    assert response.status_code==200,response.json
    task=response.json
    assert task['status']=='waiting_for_review'
    assert client.get('/api/partnership/continuations?business_id=b').json['items'][0]['id']==task['id']
    assert client.post('/api/partnership/continuations/'+task['id'],json={'business_id':'b','action':'start','revision':task['revision']}).json['status']=='queued'
    monkeypatch.setattr(access_schema,'_require_auth',lambda:({'user_id':'u2','is_active':True},None))
    cur.execute("INSERT INTO business_members VALUES ('b','u2','viewer','active')")
    assert client.post('/api/partnership/continuations/'+task['id'],json={'business_id':'b','action':'pause','revision':task['revision']}).status_code==403


def test_misconfigured_gateway_never_starts_paid_search(execution,monkeypatch):
    _,cur,tick=execution
    monkeypatch.delenv('LLM_ROUTER_ENABLED')
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())
    outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='start',revision=task['revision'])
    monkeypatch.setattr(outreach_continuation,'_start_search',lambda *a:pytest.fail('Paid search must not start without model route'))
    assert tick()['status']=='pending_human'
    state=outreach_continuation.list_tasks(cur,business_id='b',user_id='u')[0]['state']
    assert state['search_calls']==0 and state['blocker']=='draft_model_not_enabled'


def test_shortage_wakes_same_task_but_never_resumes_paused_or_running(db,monkeypatch):
    _,cur=db
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED','true')
    monkeypatch.setenv('OUTREACH_CONTINUATION_BUSINESS_IDS','b')
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())
    # Exercise durable wake query independently from Riderra's read-only run journal.
    cur.execute("UPDATE operator_async_jobs SET payload_json=payload_json || %s, result_json=result_json || %s, status='queued',next_attempt_at=NOW()+INTERVAL '1 day' WHERE id=%s",(Json({'riderra_shortage_only':True}),Json({'started':True,'phase':'search'}),task['id']))
    assert outreach_continuation.wake_after_riderra_shortage(cur,business_id='b',run_id='run')==1
    cur.execute("SELECT * FROM operator_async_jobs WHERE id=%s",(task['id'],))
    current=outreach_continuation.view(dict(cur.fetchone()))
    outreach_continuation.control_task(cur,task_id=task['id'],business_id='b',user_id='u',action='pause',revision=current['revision'])
    assert outreach_continuation.wake_after_riderra_shortage(cur,business_id='b',run_id='run')==0
    assert outreach_continuation.list_tasks(cur,business_id='b',user_id='u')[0]['status']=='waiting_for_review'


def test_contract_survives_overwritten_search_metadata(execution):
    _,cur,_=execution
    task=outreach_continuation.create_task(cur,business_id='b',user_id='u',config=config())
    cur.execute("INSERT INTO prospectingleads VALUES ('l','b','https://example.org','{}')")
    cur.execute("INSERT INTO lead_workstreams VALUES ('w','l','b','new')")
    cur.execute('UPDATE operator_async_jobs SET result_json=result_json || %s WHERE id=%s',(Json({'lead_ids':['l'],'workstream_ids':['w'],'qualifications':{'w':{'status':'qualified'}}}),task['id']))
    contract=outreach_continuation.load_workstream_contract(cur,'w')
    assert contract['task_id']==task['id']
    assert contract['qualification']['status']=='qualified'
    cur.execute("UPDATE prospectingleads SET business_id='b2' WHERE id='l'")
    assert outreach_continuation.load_workstream_contract(cur,'w') is None
