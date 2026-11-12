"""Business adapters retain native jobs and never widen a shared source."""
import json
from unittest.mock import Mock

import pytest
from flask import Blueprint, Flask

from api import operator_platform_outreach_api
from services import business_permissions, operator_async_jobs, operator_platform_outreach


class Cursor:
    def __init__(self):
        self.queries=[]
        self.rows=[]
        self.sources=[]
    def execute(self,query,params=()):
        self.queries.append((query,params))
        self.rows=self.sources if 'SELECT DISTINCT sender.id AS sender_account_id' in query else []
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


@pytest.fixture
def setup(monkeypatch):
    cursor=Cursor(); database=Mock(); database.conn.cursor.return_value=cursor
    actor={'user_id':'owner','is_superadmin':True,'messenger_platform':'max'}
    monkeypatch.setattr(operator_platform_outreach_api,'require_auth_from_request',lambda:actor)
    monkeypatch.setattr(operator_platform_outreach_api,'DatabaseManager',lambda:database)
    current={'user_id':'owner','id':'owner','is_active':True,'is_superadmin':False}
    monkeypatch.setattr(business_permissions,'load_actor',lambda *args:current)
    monkeypatch.setattr('services.partnership_leads_service.get_capability_access',lambda *args:{'allowed':True})
    access=Mock(side_effect=lambda cursor,business,user:(business=='business-a','owner'))
    monkeypatch.setattr('core.auth_helpers.verify_business_access',access)
    write=Mock(side_effect=lambda cursor,business,user:(business=='business-a','owner'))
    monkeypatch.setattr('core.auth_helpers.verify_business_write_access',write)
    app=Flask(__name__); bp=Blueprint('business_outreach',__name__)
    operator_platform_outreach_api.register_platform_outreach_routes(bp);app.register_blueprint(bp)
    return app.test_client(),cursor,database,actor,current,write


def test_business_workspace_filters_every_private_list_and_does_not_start_work(setup,monkeypatch):
    client,cursor,database,actor,current,_=setup
    monkeypatch.setattr('services.outreach_web_search.configured',lambda *args:False)
    response=client.get('/mobile/outreach?scope_kind=business&scope_id=business-a')
    assert response.status_code==200
    assert response.json['scope']=={'kind':'business','id':'business-a'}
    assert response.json['can_write'] is True
    assert response.json['active_job'] is None
    queries=cursor.queries
    inbox=next(item for item in queries if 'FROM outreach_inbound_events inbound' in item[0])
    assert inbox[1]==('business-a',21)
    assert 'COALESCE(workstream.client_business_id,campaign.business_id)=%s' in inbox[0]
    assert 'campaign.business_id=workstream.client_business_id' in inbox[0]
    senders=next(item for item in queries if 'FROM outreach_sender_accounts sender LEFT JOIN businesses' in item[0])
    assert "OR (sender.scope_type='platform' AND EXISTS" in senders[0]
    searches=next(item for item in queries if "job.kind='outreach_continue'" in item[0])
    assert searches[1]==('business-a','owner')
    job=next(item for item in queries if 'SELECT * FROM operator_async_jobs' in item[0])
    assert job[1]==('outreach_inbox_sync','business-a','owner')
    assert not any('INSERT' in query for query,_ in queries)
    database.conn.commit.assert_not_called()


@pytest.mark.parametrize('action',['sync','search_preview'])
def test_viewer_can_read_but_not_start_live_work(setup,monkeypatch,action):
    client,cursor,db,_,_,write=setup
    write.side_effect=None;write.return_value=(False,'owner')
    monkeypatch.setattr('services.outreach_web_search.configured',lambda *args:False)
    assert client.get('/mobile/outreach?scope_kind=business&scope_id=business-a').json['can_write'] is False
    response=client.post('/mobile/outreach',json={'scope_kind':'business','scope_id':'business-a','action':action})
    assert response.status_code==403
    assert not any('INSERT' in query for query,_ in cursor.queries)
    db.conn.commit.assert_not_called()


@pytest.mark.parametrize('restriction',[{'session_kind':'demo'},{'impersonating':True},{'impersonated_by':'admin'}])
def test_restricted_session_cannot_read_or_start_real_business_sources(setup,restriction):
    client,cursor,_,actor,_,_=setup
    actor.update(restriction)
    assert client.get('/mobile/outreach?scope_kind=business&scope_id=business-a').status_code==403
    assert not cursor.queries


def test_business_alias_rejects_foreign_target_and_cached_admin_flag(setup):
    client,cursor,*_=setup
    assert client.get('/mobile/outreach?scope_kind=business&scope_id=business-b').status_code==403
    assert client.post('/mobile/outreach',json={'scope_kind':'business','scope_id':'business-a',
        'target_business_id':'business-b','action':'sync'}).status_code==403
    assert not cursor.queries


def test_revoked_actor_rejected_before_private_data(setup,monkeypatch):
    client,cursor,*_=setup
    monkeypatch.setattr(business_permissions,'load_actor',Mock(side_effect=PermissionError('revoked')))
    assert client.get('/mobile/outreach?scope_kind=business&scope_id=business-a').status_code==403
    assert not cursor.queries


def test_client_sync_queues_verified_sources_without_provider_read(setup,monkeypatch):
    client,cursor,db,*_=setup
    cursor.sources=[{'sender_account_id':'shared-sender','channel':'email','campaign_id':'campaign-a'}]
    create=Mock(return_value={'id':'sync-job','status':'queued','kind':'outreach_inbox_sync'})
    monkeypatch.setattr(operator_async_jobs,'create_operator_async_job',create)
    monkeypatch.setattr(operator_platform_outreach,'sync_reply_channels',Mock(side_effect=AssertionError('provider inside request')))
    payload={'scope_kind':'business','scope_id':'business-a','action':'sync','request_id':'same',
             'sources':[{'sender_account_id':'foreign'}]}
    response=client.post('/mobile/outreach',json=payload)
    assert response.status_code==200
    assert create.call_args.kwargs['payload']['sources']==cursor.sources
    assert create.call_args.kwargs['business_id']=='business-a'
    assert create.call_args.kwargs['max_attempts']==1
    db.conn.commit.assert_called_once()
    key=create.call_args.kwargs['idempotency_key']
    client.post('/mobile/outreach',json=payload)
    assert create.call_args.kwargs['idempotency_key']==key
    payload['request_id']='new-check';client.post('/mobile/outreach',json=payload)
    assert create.call_args.kwargs['idempotency_key']!=key


def test_scoped_collectors_always_receive_sender_and_campaign(monkeypatch):
    email=Mock(return_value={'picked':1});vk=Mock(return_value={'picked':1});telegram=Mock(return_value={'picked':1})
    monkeypatch.setattr('services.outreach_email_reply_service.sync_email_replies',email)
    monkeypatch.setattr('services.outreach_vk_reply_service.sync_vk_replies',vk)
    monkeypatch.setattr('api.admin_prospecting._sync_telegram_app_replies',telegram)
    monkeypatch.setattr('services.outreach_reply_scope_guard.assert_campaign_peer_isolation',lambda *args:None)
    for channel,collect in operator_platform_outreach.sync_reply_channels([
        {'channel':channel,'sender_account_id':'shared','campaign_id':'campaign-a'}
        for channel in ('email','vk','telegram')]):
        collect()
    for provider in (email,vk,telegram):
        assert provider.call_args.kwargs['sender_account_id']=='shared'
        assert provider.call_args.kwargs['campaign_id']=='campaign-a'


def test_worker_checks_source_ownership_again_before_any_provider(setup,monkeypatch):
    _,cursor,*_=setup
    connection=Mock();connection.cursor.return_value=cursor
    monkeypatch.setattr('pg_db_utils.get_db_connection',lambda:connection)
    providers=Mock();monkeypatch.setattr(operator_platform_outreach,'sync_reply_channels',providers)
    job={'business_id':'business-a','user_id':'owner','payload_json':{'scope_kind':'business','scope_id':'business-a',
        'sources':[{'sender_account_id':'old-shared','channel':'email','campaign_id':'campaign-a'}]}}
    with pytest.raises(PermissionError):operator_platform_outreach.process_reply_sync(job)
    providers.assert_not_called()


def test_foreign_cursor_does_not_advance_business_inbox():
    cursor=Cursor()
    page=operator_platform_outreach.inbox_page(cursor,business_id='business-a',before='00000000-0000-0000-0000-000000000001')
    assert page=={'items':[],'cursor':None}
    assert len(cursor.queries)==1
    assert cursor.queries[0][1]==('00000000-0000-0000-0000-000000000001','business-a')


def test_business_search_uses_actual_chat_approval_and_current_actor(setup,monkeypatch):
    from services import operator_chat_service,outreach_continuation,partnership_leads_service
    client,_,_,actor,current,_=setup
    monkeypatch.setenv('OUTREACH_CONTINUATION_ENABLED','true')
    monkeypatch.setenv('OUTREACH_CONTINUATION_BUSINESS_IDS','business-a')
    monkeypatch.setattr(partnership_leads_service,'get_capability_access',lambda *args:{'allowed':True})
    monkeypatch.setattr('services.outreach_web_search.configured',lambda *args:True)
    monkeypatch.setattr('services.operator_request_history.enabled',lambda *args:False)
    monkeypatch.setattr('services.operator_workday.enabled',lambda *args:False)
    monkeypatch.setattr('services.operator_followups.remember_selection',lambda *args,**kwargs:None)
    for name,value in {'find_latest_operator_conversation':{},'get_or_create_operator_conversation':{'id':'conversation'},
        'conversation_pending_context':{},'list_operator_messages':[],'list_pending_operator_actions':[]}.items():
        monkeypatch.setattr(operator_chat_service,name,Mock(return_value=value))
    monkeypatch.setattr(operator_chat_service,'append_operator_message',Mock(return_value='message'))
    monkeypatch.setattr(operator_chat_service,'set_operator_pending_context',Mock())
    approval=Mock(return_value={'id':'saved-approval'});monkeypatch.setattr(operator_chat_service,'create_pending_operator_action',approval)
    create=Mock(side_effect=AssertionError('search before confirm'));monkeypatch.setattr(outreach_continuation,'create_task',create)
    response=client.post('/mobile/outreach',json={'scope_kind':'business','scope_id':'business-a','action':'search_preview',
        'audience':'travel planners','search_geography':['United States'],'target_count':3,'request_id':'search-preview'})
    assert response.status_code==200
    assert response.json['business_id']=='business-a'
    assert response.json['operator_result']['approval']['action_id']=='saved-approval'
    assert approval.call_args.kwargs['business_id']=='business-a'
    assert approval.call_args.kwargs['envelope']['config']['mode']=='find_only'
    create.assert_not_called()


def test_client_tariff_gate_prevents_private_workspace_and_sync(setup,monkeypatch):
    client,cursor,*_=setup
    monkeypatch.setattr('services.partnership_leads_service.get_capability_access',lambda *args:{'allowed':False})
    assert client.get('/mobile/outreach?scope_kind=business&scope_id=business-a').status_code==403
    assert client.post('/mobile/outreach',json={'scope_kind':'business','scope_id':'business-a','action':'sync'}).status_code==403
    assert not cursor.queries


def test_campaign_email_collision_blocks_before_mailbox_reads(monkeypatch):
    from services import outreach_email_reply_service
    cursor=Mock();cursor.fetchone.return_value={'ambiguous':True}
    connection=Mock();connection.cursor.return_value=cursor
    monkeypatch.setattr(outreach_email_reply_service,'get_db_connection',lambda:connection)
    with pytest.raises(outreach_email_reply_service.EmailAdapterError) as error:
        outreach_email_reply_service._assert_campaign_recipient_isolation('shared','campaign-a')
    assert error.value.code=='email_reply_cross_business_recipient_ambiguous'
    query,params=cursor.execute.call_args.args
    assert 'other_campaign.business_id IS DISTINCT FROM requested_campaign.business_id' in query
    assert params==('shared','campaign-a')
    connection.close.assert_called_once()


def test_scoped_legacy_email_reads_only_campaign_recipients_and_keeps_sender_watermark(monkeypatch):
    from services import outreach_email_reply_service as service
    from datetime import datetime,timezone
    monkeypatch.setattr(service,'_load_non_author_queue_candidates',lambda *args,**kwargs:[{'recipient_value':'allowed@example.test'}])
    fetch=Mock(return_value={'messages':[]});monkeypatch.setattr(service,'fetch_complete_mailbox_window',fetch)
    forbidden=Mock(side_effect=AssertionError('unscoped mailbox read'))
    monkeypatch.setattr(service,'fetch_replies',forbidden);monkeypatch.setattr(service,'fetch_mailbox_messages',forbidden)
    monkeypatch.setattr(service,'_sync_known_email_threads',forbidden)
    cursor=Mock();connection=Mock();connection.cursor.return_value=cursor
    monkeypatch.setattr(service,'get_db_connection',lambda:connection)
    result=service._sync_legacy_non_author_sender({'id':'shared','last_reply_sync_at':datetime.now(timezone.utc)},campaign_id='campaign-a',limit=10)
    assert result['failed']==0
    for call in fetch.call_args_list:
        assert call.kwargs['recipient_emails']==['allowed@example.test']
        assert call.kwargs['max_messages']==10
    assert not any('UPDATE outreach_sender_accounts' in call.args[0] for call in cursor.execute.call_args_list)
    forbidden.assert_not_called()


def test_telegram_campaign_scope_disables_global_thread_fallback(monkeypatch):
    from api import admin_prospecting
    cursor=Mock();cursor.fetchall.return_value=[]
    connection=Mock();connection.cursor.return_value=cursor
    monkeypatch.setattr(admin_prospecting,'get_db_connection',lambda:connection)
    monkeypatch.setenv('OUTREACH_TELEGRAM_THREAD_SYNC_ENABLED','true')
    monkeypatch.setenv('OUTREACH_THREAD_SYNC_BUSINESS_IDS','foreign-business')
    items=admin_prospecting._load_telegram_reply_sync_candidates(sender_account_id='shared',campaign_id='campaign-a')
    assert items==[]
    assert cursor.execute.call_count==1
    query,params=cursor.execute.call_args.args
    assert 'campaign_touch_id IN (SELECT id FROM outreach_campaign_touches WHERE campaign_id=%s)' in query
    assert 'campaign-a' in params and 'shared' in params


def test_business_chat_distinguishes_saved_read_and_fresh_check(setup,monkeypatch):
    _,cursor,_,actor,*_=setup
    queue=Mock(return_value={'id':'durable-sync'});monkeypatch.setattr(operator_platform_outreach,'enqueue_reply_sync',queue)
    saved=operator_platform_outreach.business_read_request(cursor,business_id='business-a',user_id='owner',message='Покажи входящие',actor=actor)
    assert saved['status']=='completed' and saved['sync_checked'] is False
    queue.assert_not_called()
    fresh=operator_platform_outreach.business_read_request(cursor,business_id='business-a',user_id='owner',message='Проверь входящие',actor=actor,request_id='stable')
    assert fresh['async_job_id']=='durable-sync'
    assert queue.call_args.kwargs['request_id']=='stable'
    assert queue.call_args.kwargs['scope']['business_id']=='business-a'
    assert operator_platform_outreach.business_read_request(cursor,business_id='business-a',user_id='owner',message='Отправь ответ на входящее',actor=actor) is None


@pytest.mark.parametrize('channel',['telegram','vk'])
def test_shared_social_peer_collision_fails_before_provider(monkeypatch,channel):
    from services import outreach_reply_scope_guard
    cursor=Mock();cursor.fetchone.return_value={'ambiguous':True}
    connection=Mock();connection.cursor.return_value=cursor
    monkeypatch.setattr('pg_db_utils.get_db_connection',lambda:connection)
    provider=Mock(side_effect=AssertionError('provider called for ambiguous peer'))
    monkeypatch.setattr('api.admin_prospecting._sync_telegram_app_replies',provider)
    monkeypatch.setattr('services.outreach_vk_reply_service.sync_vk_replies',provider)
    collectors=operator_platform_outreach.sync_reply_channels([{'sender_account_id':'shared','campaign_id':'campaign-a','channel':channel}])
    with pytest.raises(PermissionError):collectors[0][1]()
    provider.assert_not_called()
    query,params=cursor.execute.call_args.args
    assert 'other_campaign.business_id IS DISTINCT FROM requested_campaign.business_id' in query
    assert params==('shared','campaign-a',channel)
