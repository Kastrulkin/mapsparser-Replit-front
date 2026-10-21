from types import SimpleNamespace
import uuid

import pytest
from psycopg2.extras import Json

from tests.test_outreach_ai_authorization_pg import permission, confirm
from tests.test_outreach_continuation_pg import db
from services import outreach_ai_campaigns, outreach_campaign_service, outreach_continuation


@pytest.fixture
def campaign(permission,monkeypatch):
    conn,cursor,rules = permission
    grant = confirm(cursor,rules)
    cid,tid,contact = (str(uuid.uuid4()) for _ in range(3))
    cursor.execute('CREATE TABLE outreach_campaigns(id UUID PRIMARY KEY,business_id TEXT,lead_id TEXT,workstream_id TEXT,status TEXT,policy_json JSONB,updated_at TIMESTAMPTZ)')
    cursor.execute('CREATE TABLE outreach_campaign_touches(id UUID PRIMARY KEY,campaign_id UUID,sender_account_id UUID,contact_point_id UUID,sequence_index INT,channel TEXT,subject TEXT,generated_text TEXT,message_brief_json JSONB,quality_gate_json JSONB)')
    cursor.execute('CREATE TABLE outreach_campaign_events(id UUID PRIMARY KEY,campaign_id UUID,touch_id UUID,event_type TEXT,reason_code TEXT,payload_json JSONB,actor_id TEXT,created_at TIMESTAMPTZ)')
    cursor.execute('CREATE TABLE lead_contact_points(id UUID PRIMARY KEY,lead_id TEXT,contact_type TEXT,verification_status TEXT,stale_after TIMESTAMPTZ)')
    cursor.execute('CREATE TABLE lead_workstream_research(workstream_id TEXT,evidence_json JSONB,researched_at TIMESTAMPTZ,created_at TIMESTAMPTZ)')
    cursor.execute("INSERT INTO outreach_campaigns VALUES(%s,%s,'lead','ws','draft','{}',NOW())",(cid,rules['business_id']))
    cursor.execute("INSERT INTO outreach_campaign_touches VALUES(%s,%s,%s,%s,0,'email','Transfer','Prebooked transfers','{}','{\"passed\":true}')",(tid,cid,rules['sender_account_id'],contact))
    cursor.execute("INSERT INTO lead_contact_points VALUES(%s,'lead','email','verified',NULL)",(contact,))
    cursor.execute("INSERT INTO lead_workstream_research VALUES('ws',%s,NOW(),NOW())",(Json([{'fact':'Agency in India sells trips to Phuket','source_url':'https://example.com','source_type':'public'}]),))
    state = {'started':True,'qualifications':{'ws':{'status':'qualified'}},'verified_contact_workstream_ids':['ws'],
             'campaign_results':{'ws':{'campaign_id':cid}},'ai_authorization_id':str(grant['id'])}
    cursor.execute("UPDATE operator_async_jobs SET status='running',lease_token='lease',result_json=%s WHERE id='job'",(Json(state),))
    monkeypatch.setattr('services.outreach_personalization_ai.generation_contract_current',lambda *args,**kwargs:True)
    conn.commit()
    return conn,cursor,rules,grant,cid,state


def approved_model(request):
    return SimpleNamespace(status='completed',provider='deepseek',content='{"language_correct":true,"claims_supported":true,"audience_supported":true,"suitable_first_email":true,"reason":"supported"}')


def test_review_is_bound_to_exact_text_and_live_grant(campaign):
    conn,cursor,rules,grant,cid,state = campaign
    result = outreach_ai_campaigns.review(cursor,campaign_id=cid,job_id='job',authorization_id=str(grant['id']),user_id='u',runner=approved_model)
    assert result['passed']
    conn.commit()
    stored,touches = outreach_ai_campaigns._campaign(cursor,cid)
    assert outreach_ai_campaigns.validate(cursor,campaign=stored,touches=touches,authorization_id=str(grant['id']),job_id='job')
    cursor.execute("UPDATE outreach_campaign_touches SET generated_text='Invented discount' WHERE campaign_id=%s",(cid,))
    _,touches = outreach_ai_campaigns._campaign(cursor,cid)
    assert outreach_ai_campaigns.validate(cursor,campaign=stored,touches=touches,authorization_id=str(grant['id']),job_id='job') is None
    conn.rollback()
    confirm(cursor,rules,action='revoke',enabled=False)
    stored,touches = outreach_ai_campaigns._campaign(cursor,cid)
    assert outreach_ai_campaigns.validate(cursor,campaign=stored,touches=touches,authorization_id=str(grant['id']),job_id='job') is None


def test_unknown_review_fails_closed_without_native_approval(campaign):
    _,cursor,_,grant,cid,_ = campaign
    result = outreach_ai_campaigns.review(cursor,campaign_id=cid,job_id='job',authorization_id=str(grant['id']),user_id='u',
        runner=lambda request:SimpleNamespace(status='completed',provider='deepseek',content='[]'))
    assert result['passed'] is False
    with pytest.raises(ValueError,match='authorization_or_review_changed'):
        outreach_ai_campaigns.approve(cursor,campaign_id=cid,job_id='job',authorization_id=str(grant['id']))


def test_native_approval_is_called_only_after_bound_review(campaign,monkeypatch):
    _,cursor,_,grant,cid,_ = campaign
    outreach_ai_campaigns.review(cursor,campaign_id=cid,job_id='job',authorization_id=str(grant['id']),user_id='u',runner=approved_model)
    calls=[]
    monkeypatch.setattr(outreach_campaign_service,'approve_campaign',lambda cursor,campaign_id,**kwargs:calls.append(kwargs) or {'id':campaign_id,'status':'approved'})
    assert outreach_ai_campaigns.approve(cursor,campaign_id=cid,job_id='job',authorization_id=str(grant['id']))['status']=='approved'
    assert calls[0]['user_id'] is None and str(calls[0]['ai_authorization']['id'])==str(grant['id'])
    cursor.execute('SELECT policy_json FROM outreach_campaigns WHERE id=%s',(cid,))
    assert cursor.fetchone()['policy_json']['approval_mode']=='ai_rules'


def test_review_reservation_retains_lease_and_bad_letter_does_not_stop_job(campaign,monkeypatch):
    conn,cursor,_,grant,cid,state = campaign
    cursor.execute("SELECT * FROM operator_async_jobs WHERE id='job'")
    row=dict(cursor.fetchone())
    seen=[]
    def review(cursor,**kwargs):
        cursor.execute("SELECT status,lease_token,result_json FROM operator_async_jobs WHERE id='job'")
        current=cursor.fetchone()
        seen.append(current)
        return {'passed':False,'reason':'unsupported_claim'}
    monkeypatch.setattr(outreach_ai_campaigns,'review',review)
    monkeypatch.setattr(outreach_continuation,'_require_current_actor',lambda *args:None)
    assert outreach_continuation.advance_ai_campaign(conn,cursor,row,state,{**grant,'rules':row['payload_json'] | {'max_draft_attempts':100},'id':grant['id']})
    assert seen[0]['status']=='running' and seen[0]['lease_token']=='lease'
    assert seen[0]['result_json']['ai_review_attempts']==1
    cursor.execute("SELECT status,result_json FROM operator_async_jobs WHERE id='job'")
    current=cursor.fetchone()
    assert current['status']=='queued'
    assert current['result_json']['campaign_results']['ws']['ai_review_status']=='needs_review'


def test_same_rules_regrant_reviews_for_new_permission(campaign,monkeypatch):
    _,cursor,rules,grant,cid,_=campaign
    monkeypatch.setattr('services.outreach_language_routing.run_copy',lambda *args,**kwargs:'{"language_correct":true,"claims_supported":true,"audience_supported":true,"suitable_first_email":true}')
    first=outreach_ai_campaigns.review(cursor,campaign_id=cid,job_id='job',authorization_id=str(grant['id']),user_id='u')
    confirm(cursor,rules,action='revoke',enabled=False)
    second_grant=confirm(cursor,rules,action='regrant')
    second=outreach_ai_campaigns.review(cursor,campaign_id=cid,job_id='job',authorization_id=str(second_grant['id']),user_id='u')
    assert second['passed'] and second['authorization_id']==str(second_grant['id'])
    assert second['authorization_id']!=first['authorization_id']


def test_busy_preflight_retries_without_pausing_campaign(campaign):
    from services.outreach_safety_service import block_queue_item_after_preflight
    _,cursor,_,_,cid,_=campaign
    cursor.execute('CREATE TABLE outreachsendqueue(preflight_at TIMESTAMPTZ,id TEXT,delivery_status TEXT,next_retry_at TIMESTAMPTZ,attempts INT,error_text TEXT,preflight_reason TEXT,updated_at TIMESTAMPTZ)')
    cursor.execute("INSERT INTO outreachsendqueue(id,delivery_status,next_retry_at,attempts,error_text,preflight_reason,updated_at) VALUES('q','sending',NULL,1,NULL,NULL,NOW())")
    block_queue_item_after_preflight(cursor,'q',{'reason_code':'ai_rules_permission_busy','item':{'campaign_id':cid}})
    cursor.execute("SELECT delivery_status,attempts,next_retry_at FROM outreachsendqueue WHERE id='q'")
    row=cursor.fetchone()
    assert row['delivery_status']=='retry' and row['attempts']==0 and row['next_retry_at']
    cursor.execute('SELECT status FROM outreach_campaigns WHERE id=%s',(cid,))
    assert cursor.fetchone()['status']=='draft'


def test_native_approval_really_creates_one_queue_item_and_replay_does_not_duplicate(campaign,monkeypatch):
    _,cur,rules,grant,cid,_=campaign
    # Native SQL and campaign approval are real; only the language-model output
    # and its already separately tested generation contract are controlled.
    cur.execute('CREATE TABLE lead_workstreams(id TEXT,workstream_type TEXT)')
    cur.execute("INSERT INTO lead_workstreams VALUES('ws','client_partnership')")
    cur.execute('ALTER TABLE outreach_sender_accounts ADD COLUMN external_account_id TEXT')
    cur.execute('CREATE TABLE telegram_account_permissions(account_id TEXT,outreach_enabled BOOLEAN)')
    cur.execute("""ALTER TABLE outreach_campaigns ADD COLUMN scope_type TEXT DEFAULT 'business',
      ADD COLUMN version INT DEFAULT 1,ADD COLUMN sender_mode TEXT DEFAULT 'partner_business',
      ADD COLUMN sender_profile_id TEXT,ADD COLUMN approved_by TEXT,ADD COLUMN approved_at TIMESTAMPTZ,
      ADD COLUMN approved_snapshot_hash TEXT""")
    cur.execute("""ALTER TABLE outreach_campaign_touches ADD COLUMN angle_type TEXT DEFAULT 'business_reputation',
      ADD COLUMN scheduled_at TIMESTAMPTZ DEFAULT NOW(),ADD COLUMN status TEXT DEFAULT 'draft',
      ADD COLUMN approved_text TEXT,ADD COLUMN updated_at TIMESTAMPTZ,ADD COLUMN draft_id TEXT""")
    cur.execute("ALTER TABLE lead_workstream_research ADD COLUMN signals_json JSONB DEFAULT '[]',ADD COLUMN report_hash TEXT DEFAULT 'report'")
    cur.execute("SELECT evidence_json,signals_json,report_hash FROM lead_workstream_research WHERE workstream_id='ws'")
    source_hash=outreach_campaign_service.research_source_fact_fingerprint(dict(cur.fetchone()))
    cur.execute("UPDATE outreach_campaign_touches SET message_brief_json=%s",(Json({'source_fact_fingerprint':source_hash}),))
    cur.execute('CREATE TABLE outreachsendbatches(id TEXT,batch_date DATE,daily_limit INT,status TEXT,created_by TEXT,approved_by TEXT,created_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)')
    cur.execute('''CREATE TABLE outreachmessagedrafts(id TEXT,lead_id TEXT,workstream_id TEXT,channel TEXT,angle_type TEXT,tone TEXT,status TEXT,
      generated_text TEXT,approved_text TEXT,message_brief_json JSONB,quality_gate_json JSONB,contact_point_id UUID,
      sender_profile_id TEXT,created_by TEXT,approved_by TEXT,created_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)''')
    cur.execute('''CREATE TABLE outreachsendqueue(id TEXT,batch_id TEXT,lead_id TEXT,workstream_id TEXT,draft_id TEXT,channel TEXT,
      delivery_status TEXT,sender_account_id UUID,campaign_touch_id UUID,scheduled_at TIMESTAMPTZ,recipient_key TEXT,
      idempotency_key TEXT UNIQUE,created_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)''')
    monkeypatch.setattr(outreach_campaign_service,'generation_contract_current',lambda *args,**kwargs:True)
    proof=outreach_ai_campaigns.review(cur,campaign_id=cid,job_id='job',authorization_id=str(grant['id']),user_id='u',runner=approved_model)
    assert proof['passed']
    result=outreach_ai_campaigns.approve(cur,campaign_id=cid,job_id='job',authorization_id=str(grant['id']))
    assert result['approval_mode']=='ai_rules'
    cur.execute('SELECT delivery_status,sender_account_id,idempotency_key FROM outreachsendqueue')
    queued=cur.fetchall()
    assert len(queued)==1 and queued[0]['delivery_status']=='queued' and str(queued[0]['sender_account_id'])==rules['sender_account_id']
    result=outreach_ai_campaigns.approve(cur,campaign_id=cid,job_id='job',authorization_id=str(grant['id']))
    assert result['replayed']
    cur.execute('SELECT COUNT(*) n FROM outreachsendqueue')
    assert cur.fetchone()['n']==1
    confirm(cur,rules,action='revoke-native',enabled=False)
    with pytest.raises(ValueError,match='authorization_or_review_changed'):
        outreach_ai_campaigns.approve(cur,campaign_id=cid,job_id='job',authorization_id=str(grant['id']))


def test_stopped_automation_never_sends_old_completed_job_after_resume(campaign):
    _,cur,rules,grant,cid,state=campaign
    cur.execute('CREATE TABLE agent_blueprints(id TEXT,business_id TEXT,status TEXT,metadata_json JSONB)')
    cur.execute('CREATE TABLE agent_runs(id TEXT,blueprint_id TEXT,blueprint_version_id TEXT,business_id TEXT)')
    cur.execute("INSERT INTO agent_blueprints VALUES('bp',%s,'active','{}')",(rules['business_id'],))
    cur.execute("INSERT INTO agent_runs VALUES('run','bp','v1',%s)",(rules['business_id'],))
    cur.execute("UPDATE operator_async_jobs SET status='completed',result_json=result_json || '{\"agent_run_id\":\"run\"}'::jsonb WHERE id='job'")
    automation_grant={**grant,'rules':{**rules,'process':{'type':'automation','id':'bp','revision':'v1'}}}
    stored,touches=outreach_ai_campaigns._campaign(cur,cid)
    assert outreach_ai_campaigns._binding(cur,stored,touches,automation_grant,'job')
    cur.execute("UPDATE agent_blueprints SET metadata_json=jsonb_build_object('outreach_stopped_at',clock_timestamp())")
    # Status is active again, but the queue proof of the pre-stop run is invalid.
    assert not outreach_ai_campaigns._binding(cur,stored,touches,automation_grant,'job')
    cur.execute("UPDATE operator_async_jobs SET created_at=clock_timestamp()+INTERVAL '1 second' WHERE id='job'")
    assert outreach_ai_campaigns._binding(cur,stored,touches,automation_grant,'job')
