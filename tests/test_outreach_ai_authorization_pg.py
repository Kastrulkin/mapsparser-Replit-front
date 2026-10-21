"""New AI rules use the existing permission journal, not template authority."""
from copy import deepcopy

import pytest
from psycopg2.extras import Json

from tests.test_outreach_continuation_pg import db
from services import outreach_ai_authorization as auth
from services.outreach_continuation import config_hash


@pytest.fixture
def permission(db):
    conn, cursor = db
    cursor.execute("UPDATE users SET is_superadmin=TRUE WHERE id='u'")
    cursor.execute('INSERT INTO businesses(id,owner_id) VALUES(%s,%s)', (auth.BUSINESS_ID, 'u'))
    cursor.execute('ALTER TABLE operatoractions ADD COLUMN user_id TEXT,ADD COLUMN business_id TEXT,ADD COLUMN capability TEXT,ADD COLUMN envelope_json JSONB,ADD COLUMN status TEXT,ADD COLUMN expires_at TIMESTAMPTZ')
    cursor.execute('CREATE TABLE outreach_sender_accounts(id UUID PRIMARY KEY,business_id TEXT,owner_user_id TEXT,status TEXT,outreach_enabled BOOLEAN,health_status TEXT,capabilities_json JSONB,scope_type TEXT,channel TEXT,sender_identity TEXT)')
    cursor.execute("INSERT INTO outreach_sender_accounts VALUES(%s,%s,'u','connected',TRUE,'healthy',%s,'business','email','riderracs@gmail.com')",
                   (auth.SENDER_ACCOUNT_ID, auth.BUSINESS_ID, Json({'direct_send':True,'reply_sync':True})))
    cursor.execute('CREATE TABLE outreach_sender_account_events(id UUID PRIMARY KEY,sender_account_id UUID,event_type TEXT,actor_id TEXT,payload_json JSONB,created_at TIMESTAMPTZ)')
    config = {'mode':'auto_send','audience':'travel agencies', 'agency_country':'India','sold_destination':'Phuket',
              'offer':'prebooked transfers','language':'en','target_count':100,'max_search_calls':10,
              'max_qualification_calls':500,'max_draft_attempts':100,'search_budget_cents':100}
    cursor.execute("""INSERT INTO operator_async_jobs(id,business_id,user_id,kind,status,stage,payload_json,idempotency_key)
                      VALUES('job',%s,'u','outreach_continue','queued','Search',%s,'job-test')""", (auth.BUSINESS_ID, Json(config)))
    rules = auth.normalize_rules({**config,'business_id':auth.BUSINESS_ID,'sender_account_id':auth.SENDER_ACCOUNT_ID,
        'channels':['email'],'daily_limit':200,'allowed_claims':[{'text':'Prebooked transfers','source':'https://riderra.com'}],
        'process':{'type':'one_off','id':'job','revision':config_hash(config)}})
    return conn, cursor, rules


def confirm(cursor, rules, action='a1', enabled=True):
    envelope = {'rules':rules,'rules_hash':auth.digest(rules),'enabled':enabled}
    cursor.execute("INSERT INTO operatoractions(id,user_id,business_id,capability,envelope_json,status,expires_at) VALUES(%s,'u',%s,'outreach.ai_rules',%s,'pending_approval',NOW()+INTERVAL '15 minutes')",
                   (action,auth.BUSINESS_ID,Json(envelope)))
    return auth.confirm(cursor,rules=rules,rules_hash=auth.digest(rules),actor_id='u',
                        actor_context={'session_kind':'standard'},action_id=action,enabled=enabled)


def test_grant_replay_revocation_and_template_isolation(permission):
    conn, cursor, rules = permission
    event = confirm(cursor,rules)
    conn.commit()
    assert auth.load(cursor,str(event['id']))
    replay = auth.confirm(cursor,rules=rules,rules_hash=auth.digest(rules),actor_id='u',
                          actor_context={'session_kind':'standard'},action_id='a1')
    assert replay['id'] == event['id']
    confirm(cursor,rules,action='a2',enabled=False)
    assert auth.load(cursor,str(event['id'])) is None
    cursor.execute("UPDATE operatoractions SET status='completed' WHERE id='a1'")
    with pytest.raises(PermissionError,match='already_used'):
        auth.confirm(cursor,rules=rules,rules_hash=auth.digest(rules),actor_id='u',
                     actor_context={'session_kind':'standard'},action_id='a1')
    assert auth.load(cursor,str(event['id'])) is None
    cursor.execute('SELECT COUNT(*) n FROM outreach_sender_account_events')
    assert cursor.fetchone()['n'] == 2
    cursor.execute("SELECT COUNT(*) n FROM outreach_sender_account_events WHERE payload_json->>'permission_kind' LIKE 'riderra_buyer_template%'")
    assert cursor.fetchone()['n'] == 0


def test_changed_process_pause_and_authority_block_sends(permission):
    _, cursor, rules = permission
    event = confirm(cursor,rules)
    cursor.execute("UPDATE operator_async_jobs SET status='waiting_for_review' WHERE id='job'")
    assert auth.load(cursor,str(event['id'])) is None
    cursor.execute("UPDATE operator_async_jobs SET status='running' WHERE id='job'")
    assert auth.load(cursor,str(event['id']))
    cursor.execute("UPDATE operator_async_jobs SET payload_json=payload_json || '{\"target_count\":50}' WHERE id='job'")
    assert auth.load(cursor,str(event['id'])) is None
    # Revocation remains possible after the process changed or sender disconnected.
    cursor.execute("UPDATE outreach_sender_accounts SET status='disconnected'")
    confirm(cursor,rules,action='revoke',enabled=False)
    assert auth.load(cursor,str(event['id'])) is None


def test_no_implicit_grant_from_template_or_fake_confirmation(permission):
    _, cursor, rules = permission
    with pytest.raises(PermissionError,match='explicit_confirmation'):
        auth.confirm(cursor,rules=rules,rules_hash=auth.digest(rules),actor_id='u',
                     actor_context={'session_kind':'standard'},action_id='missing')
    with pytest.raises(PermissionError,match='direct_session'):
        auth.preview(cursor,rules=rules,actor_id='u',actor_context={'session_kind':'demo'})
    with pytest.raises(PermissionError,match='authority'):
        auth.preview(cursor,rules=rules,actor_id='u2',actor_context={'session_kind':'standard'})
    changed = deepcopy(rules)
    changed['sender_account_id'] = 'other'
    with pytest.raises(ValueError,match='sender_scope'):
        auth.normalize_rules(changed)
    with pytest.raises(ValueError,match='preview_changed'):
        auth.confirm(cursor,rules=rules,rules_hash='wrong',actor_id='u',
                     actor_context={'session_kind':'standard'},action_id='missing')


def test_expired_confirmation_cannot_grant(permission):
    _, cursor, rules = permission
    envelope = {'rules':rules,'rules_hash':auth.digest(rules),'enabled':True}
    cursor.execute("INSERT INTO operatoractions(id,user_id,business_id,capability,envelope_json,status,expires_at) VALUES('expired','u',%s,'outreach.ai_rules',%s,'pending_approval',NOW()-INTERVAL '1 minute')", (auth.BUSINESS_ID,Json(envelope)))
    with pytest.raises(PermissionError,match='confirmation_expired'):
        auth.confirm(cursor,rules=rules,rules_hash=auth.digest(rules),actor_id='u',
                     actor_context={'session_kind':'standard'},action_id='expired')


def test_pinned_permission_of_another_job_cannot_authorize_work(permission):
    _, cursor, rules = permission
    event = confirm(cursor,rules)
    cursor.execute("SELECT * FROM operator_async_jobs WHERE id='job'")
    job = dict(cursor.fetchone())
    job['result_json'] = {'ai_authorization_id':str(event['id'])}
    assert auth.for_job(cursor,job)
    assert auth.for_job(cursor,{**job,'id':'other-job'}) is None
    assert auth.for_job(cursor,{**job,'payload_json':{**job['payload_json'],'agency_country':'China'}}) is None


def test_preparation_mode_cannot_become_a_send_permission(permission):
    _, cursor, rules = permission
    for mode in ('prepare_only','find_only'):
        with pytest.raises(ValueError,match='auto_send_intent_required'):
            auth.preview(cursor,rules={**rules,'mode':mode},actor_id='u',actor_context={'session_kind':'standard'})


def test_automation_grant_is_bound_to_run_version_and_pause(permission):
    _, cursor, rules = permission
    cursor.execute("SELECT * FROM operator_async_jobs WHERE id='job'")
    job = dict(cursor.fetchone())
    cursor.execute('CREATE TABLE agent_blueprints(id TEXT,business_id TEXT,status TEXT,metadata_json JSONB)')
    cursor.execute('CREATE TABLE agent_blueprint_versions(id TEXT,blueprint_id TEXT,runtime_config_json JSONB)')
    cursor.execute('CREATE TABLE agent_runs(id TEXT,business_id TEXT,blueprint_id TEXT,blueprint_version_id TEXT)')
    cursor.execute("INSERT INTO agent_blueprints VALUES('bp',%s,'active','{\"active_version_id\":\"v1\"}')",(auth.BUSINESS_ID,))
    cursor.execute("INSERT INTO agent_blueprint_versions VALUES('v1','bp',%s)",(Json({'outreach_config':job['payload_json']}),))
    cursor.execute("INSERT INTO agent_runs VALUES('run',%s,'bp','v1')",(auth.BUSINESS_ID,))
    rules = {**rules,'process':{'type':'automation','id':'bp','revision':'v1'}}
    event = confirm(cursor,rules)
    job['result_json'] = {'ai_authorization_id':str(event['id']),'agent_run_id':'run'}
    assert auth.for_job(cursor,job)
    cursor.execute("UPDATE agent_runs SET blueprint_version_id='v2'")
    assert auth.for_job(cursor,job) is None
    cursor.execute("UPDATE agent_runs SET blueprint_version_id='v1'")
    cursor.execute("UPDATE agent_blueprints SET status='paused'")
    assert auth.for_job(cursor,job) is None


@pytest.mark.parametrize('decision', [None, 'true', 1])
def test_confirmation_requires_explicit_boolean(permission, decision):
    _, cursor, rules = permission
    envelope = {'rules': rules, 'rules_hash': auth.digest(rules)}
    if decision is not None:
        envelope['enabled'] = decision
    cursor.execute("INSERT INTO operatoractions(id,user_id,business_id,capability,envelope_json,status,expires_at) VALUES('bad','u',%s,'outreach.ai_rules',%s,'pending_approval',NOW()+INTERVAL '15 minutes')", (auth.BUSINESS_ID,Json(envelope)))
    with pytest.raises(PermissionError, match='explicit_confirmation'):
        auth.confirm(cursor,rules=rules,rules_hash=auth.digest(rules),actor_id='u',
                     actor_context={'session_kind':'standard'},action_id='bad')


def test_confirmation_without_expiry_cannot_grant(permission):
    _, cursor, rules = permission
    envelope = {'rules':rules,'rules_hash':auth.digest(rules),'enabled':True}
    cursor.execute("INSERT INTO operatoractions(id,user_id,business_id,capability,envelope_json,status) VALUES('no-expiry','u',%s,'outreach.ai_rules',%s,'pending_approval')", (auth.BUSINESS_ID,Json(envelope)))
    with pytest.raises(PermissionError, match='confirmation_expired'):
        auth.confirm(cursor,rules=rules,rules_hash=auth.digest(rules),actor_id='u',
                     actor_context={'session_kind':'standard'},action_id='no-expiry')


def test_contention_is_transient_and_does_not_wait_with_job_row_lock(permission):
    import os
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn, cursor, rules = permission
    event=confirm(cursor,rules)
    conn.commit()
    cursor.execute('SELECT current_schema() AS name')
    schema=cursor.fetchone()['name']
    other=psycopg2.connect(os.environ['OUTREACH_TEST_DSN'],cursor_factory=RealDictCursor)
    try:
        with other.cursor() as second:
            from psycopg2 import sql
            second.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            assert auth._lock(second,rules)
            cursor.execute("SELECT id FROM operator_async_jobs WHERE id='job' FOR UPDATE")
            cursor.execute("SET LOCAL statement_timeout='500ms'")
            with pytest.raises(auth.AuthorizationBusy):auth.load(cursor,str(event['id']))
            cursor.execute("SELECT status FROM operator_async_jobs WHERE id='job'")
            assert cursor.fetchone()['status']=='queued'
            conn.commit()
        other.rollback()
        assert auth.load(cursor,str(event['id']))
    finally:
        other.close()


def test_native_operator_action_can_confirm_exact_rules_once(permission,monkeypatch):
    from services import operator_conversations,operator_core
    _,cur,rules=permission
    cur.execute("ALTER TABLE operatoractions ALTER COLUMN status SET DEFAULT 'pending', ADD COLUMN conversation_id TEXT, ADD COLUMN idempotency_key TEXT, ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW()")
    cur.execute('CREATE UNIQUE INDEX action_request ON operatoractions(business_id,idempotency_key)')
    preview=auth.operator_preview(cur,business_id=auth.BUSINESS_ID,user_id='u',arguments={'enabled':True,'rules':rules},actor_context={'session_kind':'standard'})
    action=operator_conversations.create_pending_operator_action(cur,conversation_id='c',business_id=auth.BUSINESS_ID,user_id='u',capability='outreach.ai_rules',envelope=preview['approval']['envelope'])
    assert action['status']=='pending' and action['expires_at'] is not None
    # Completion history is orthogonal; the action/grant SQL path stays native.
    finished=[]
    def finish(cursor,*,action_id,result):
        cursor.execute("UPDATE operatoractions SET status='completed' WHERE id=%s",(action_id,))
        finished.append(result)
    monkeypatch.setattr(operator_core,'finish_operator_action',finish)
    monkeypatch.setattr(operator_core,'operator_subscription_block',lambda *args:None)
    result,_=operator_core.confirm_pending_operator_action(cur,action_id=action['id'],business_id=auth.BUSINESS_ID,user_id='u',actor_context={'session_kind':'standard'})
    assert result['status']=='completed' and len(finished)==1
    assert auth.load(cur,result['authorization_id'])
    cur.execute('SELECT COUNT(*) n FROM outreach_sender_account_events')
    assert cur.fetchone()['n']==1


@pytest.mark.parametrize('provider_raises',[False,True])
def test_dispatch_keeps_permission_fence_across_commit_and_releases_on_error(permission,monkeypatch,provider_raises):
    import os,psycopg2
    from types import SimpleNamespace
    from psycopg2.extras import RealDictCursor
    from services import outreach_dispatch_service as dispatch
    conn,cur,rules=permission
    grant=confirm(cur,rules)
    cur.execute('SHOW search_path')
    schema=cur.fetchone()['search_path']
    conn.commit()
    used=[]
    def connection():
        db=psycopg2.connect(os.environ['OUTREACH_TEST_DSN'],cursor_factory=RealDictCursor)
        db.cursor().execute('SET search_path TO '+schema)
        used.append(db)
        return db
    policy={'approval_mode':'ai_rules','ai_authorization_id':str(grant['id'])}
    monkeypatch.setattr(dispatch,'run_dispatch_preflight',lambda *args,**kwargs:{'allowed':True,'item':{'policy_json':policy}})
    monkeypatch.setattr(dispatch,'bind_preflight_dispatch_item',lambda item,preflight:item)
    monkeypatch.setattr(dispatch,'persist_preflight_result',lambda *args:None)
    key=f"ai-outreach:{rules['sender_account_id']}:one_off:job"
    def provider(item):
        cur.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS acquired',(key,))
        assert cur.fetchone()['acquired'] is False
        if provider_raises:raise RuntimeError('provider transport uncertain')
        return {'delivery_status':'sent','provider_message_id':'test-receipt'}
    api=SimpleNamespace(get_db_connection=connection,_dispatch_outreach_queue_item=provider)
    if provider_raises:
        with pytest.raises(RuntimeError):dispatch._preflight_and_dispatch(api,{'id':'queue'})
    else:
        _,checked,result=dispatch._preflight_and_dispatch(api,{'id':'queue'})
        assert checked['allowed'] and result['provider_message_id']=='test-receipt'
    cur.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS acquired',(key,))
    assert cur.fetchone()['acquired'] is True
    assert all(db.closed for db in used)
