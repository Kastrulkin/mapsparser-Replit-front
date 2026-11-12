"""Opt-in integration against a disposable local PostgreSQL database.

LOCALOS_TEST_DATABASE_URL must address localhost and a localos_test* database.
No application/production DSN is read. The fixture creates/drops only its unique
schema; the application's real scope/inbox/queue SQL is executed there.
"""
import os
import uuid
from urllib.parse import urlparse
from unittest.mock import Mock

import pytest

from services import operator_platform_outreach


@pytest.fixture
def pg(monkeypatch):
    dsn=os.getenv('LOCALOS_TEST_DATABASE_URL','')
    if not dsn:
        pytest.skip('LOCALOS_TEST_DATABASE_URL absent; disposable PostgreSQL required')
    url=urlparse(dsn)
    if url.hostname not in {'localhost','127.0.0.1','::1'} or not url.path.lstrip('/').startswith('localos_test'):
        pytest.fail('Test DSN must be a disposable local localos_test* database')
    import psycopg2
    from psycopg2.extras import RealDictCursor
    connection=psycopg2.connect(dsn,cursor_factory=RealDictCursor)
    connection.autocommit=True
    schema='outreach_test_'+uuid.uuid4().hex
    cursor=connection.cursor();cursor.execute('CREATE SCHEMA '+schema)
    cursor.execute('SET search_path TO '+schema)
    cursor.execute('''CREATE TABLE users(id text primary key,is_active boolean,is_superadmin boolean);
      CREATE TABLE businesses(id text primary key,name text,owner_id text,is_active boolean,network_id text);
      CREATE TABLE business_members(business_id text,user_id text,status text,role text);
      CREATE TABLE network_members(network_id text,user_id text,status text,role text);
      CREATE TABLE networks(id text,owner_id text);
      CREATE TABLE prospectingleads(id text primary key,name text);
      CREATE TABLE lead_workstreams(id uuid primary key,client_business_id text);
      CREATE TABLE outreach_campaigns(id uuid primary key,business_id text,workstream_id uuid);
      CREATE TABLE outreach_campaign_touches(id uuid primary key,campaign_id uuid,sender_account_id uuid);
      CREATE TABLE outreach_inbound_events(id uuid primary key,campaign_id uuid,workstream_id uuid,
        lead_id text,channel text,classification text,is_human boolean,raw_payload_json jsonb,
        occurred_at timestamptz default now(),created_at timestamptz default now());
      CREATE TABLE outreach_sender_accounts(id uuid primary key,channel text,scope_type text,business_id text,
        sender_identity text,display_name text,status text,outreach_enabled boolean,last_reply_sync_at timestamptz,
        reply_sync_error text);
      CREATE TABLE outreachsendqueue(id uuid primary key,sender_account_id uuid,campaign_touch_id uuid,recipient_value text,channel text);
      CREATE TABLE operator_async_jobs(id uuid primary key,action_id uuid,user_id text,business_id text,kind text,
        status text default 'queued',progress int default 0,stage text,payload_json jsonb,result_json jsonb,
        idempotency_key text,max_attempts int,next_attempt_at timestamptz,created_at timestamptz default now(),
        updated_at timestamptz default now(),completed_at timestamptz,error_text text,attempt_count int default 0,
        unique(user_id,idempotency_key));
      INSERT INTO users VALUES ('owner-a',true,false),('owner-b',true,false),('viewer',true,false);
      INSERT INTO businesses VALUES ('business-a','A','owner-a',true,null),('business-b','B','owner-b',true,null);
      INSERT INTO business_members VALUES ('business-a','viewer','active','viewer');
      INSERT INTO prospectingleads VALUES ('lead-a','A lead'),('lead-b','B lead');''')
    ids={key:str(uuid.uuid4()) for key in ('work-a','work-b','campaign-a','campaign-b','sender','touch-a','touch-b','reply-a','reply-b','reply-conflict','reply-workstream')}
    for lane in ('a','b'):
        cursor.execute('INSERT INTO lead_workstreams VALUES(%s,%s)',(ids['work-'+lane],'business-'+lane))
        cursor.execute('INSERT INTO outreach_campaigns VALUES(%s,%s,%s)',(ids['campaign-'+lane],'business-'+lane,ids['work-'+lane]))
        cursor.execute('INSERT INTO outreach_campaign_touches VALUES(%s,%s,%s)',(ids['touch-'+lane],ids['campaign-'+lane],ids['sender']))
        cursor.execute("INSERT INTO outreach_inbound_events(id,campaign_id,workstream_id,lead_id,channel,is_human,raw_payload_json) VALUES(%s,%s,%s,%s,'email',true,'{}')",
            (ids['reply-'+lane],ids['campaign-'+lane],ids['work-'+lane],'lead-'+lane))
    cursor.execute("INSERT INTO outreach_inbound_events(id,campaign_id,workstream_id,lead_id,channel,is_human,raw_payload_json) VALUES(%s,%s,%s,'lead-a','email',true,'{}')",
        (ids['reply-conflict'],ids['campaign-b'],ids['work-a']))
    cursor.execute("INSERT INTO outreach_inbound_events(id,workstream_id,lead_id,channel,is_human,raw_payload_json) VALUES(%s,%s,'lead-a','email',true,'{}')",
        (ids['reply-workstream'],ids['work-a']))
    cursor.execute("INSERT INTO outreach_sender_accounts(id,channel,scope_type,status,outreach_enabled,sender_identity) VALUES(%s,'email','platform','connected',true,'shared@example.test')",(ids['sender'],))
    connection.commit()
    connection.autocommit=False
    monkeypatch.setattr('services.partnership_leads_service.get_capability_access',lambda *args:{'allowed':True})
    yield connection,cursor,ids
    connection.rollback();connection.autocommit=True
    cursor.execute('SET search_path TO public');cursor.execute('DROP SCHEMA '+schema+' CASCADE');connection.close()


def test_postgres_scope_inbox_pagination_and_source_isolation(pg):
    connection,cursor,ids=pg
    scope=operator_platform_outreach.require_outreach_scope(cursor,user_id='owner-a',scope_kind='business',scope_id='business-a',write=True)
    assert scope['can_write'] is True
    with pytest.raises(PermissionError):
        operator_platform_outreach.require_outreach_scope(cursor,user_id='owner-a',scope_kind='business',scope_id='business-b')
    viewer=operator_platform_outreach.require_outreach_scope(cursor,user_id='viewer',scope_kind='business',scope_id='business-a')
    assert viewer['can_write'] is False
    with pytest.raises(PermissionError):
        operator_platform_outreach.require_outreach_scope(cursor,user_id='viewer',scope_kind='business',scope_id='business-a',write=True)
    first=operator_platform_outreach.inbox_page(cursor,business_id='business-a',limit=1)
    second=operator_platform_outreach.inbox_page(cursor,business_id='business-a',limit=1,before=first['cursor'])
    assert {item['id'] for page in (first,second) for item in page['items']}=={ids['reply-a'],ids['reply-workstream']}
    assert operator_platform_outreach.inbox_page(cursor,business_id='business-a',before=ids['reply-b'])['items']==[]
    sources,truncated=operator_platform_outreach._business_sources(cursor,'business-a')
    assert not truncated
    assert sources==[{'sender_account_id':ids['sender'],'channel':'email','campaign_id':ids['campaign-a']}]
    cursor.execute("UPDATE users SET is_active=false WHERE id='owner-a'")
    with pytest.raises(PermissionError):
        operator_platform_outreach.require_outreach_scope(cursor,user_id='owner-a',scope_kind='business',scope_id='business-a')


def test_postgres_workspace_does_not_disclose_foreign_owned_sender_through_campaign(pg,monkeypatch):
    _,cursor,ids=pg
    monkeypatch.setattr('services.outreach_web_search.configured',lambda *args:False)
    scope=operator_platform_outreach.require_outreach_scope(cursor,user_id='owner-a',scope_kind='business',scope_id='business-a')
    cursor.execute("UPDATE outreach_sender_accounts SET scope_type='business',business_id='business-b' WHERE id=%s",(ids['sender'],))
    assert operator_platform_outreach.workspace(cursor,scope=scope,user_id='owner-a')['senders']==[]
    cursor.execute("UPDATE outreach_sender_accounts SET scope_type='platform',business_id=NULL WHERE id=%s",(ids['sender'],))
    assert [str(sender['id']) for sender in operator_platform_outreach.workspace(cursor,scope=scope,user_id='owner-a')['senders']]==[ids['sender']]


def test_postgres_native_route_sync_dedup_and_reopen(pg,monkeypatch):
    from flask import Blueprint,Flask
    from api import operator_platform_outreach_api
    connection,cursor,ids=pg
    database=Mock();database.conn=connection
    monkeypatch.setattr(operator_platform_outreach_api,'DatabaseManager',lambda:database)
    monkeypatch.setattr(operator_platform_outreach_api,'require_auth_from_request',lambda:{'user_id':'owner-a','messenger_platform':'max'})
    monkeypatch.setattr('services.outreach_web_search.configured',lambda *args:False)
    app=Flask(__name__);bp=Blueprint('outreach_postgres',__name__)
    operator_platform_outreach_api.register_platform_outreach_routes(bp);app.register_blueprint(bp)
    with app.test_client() as client:
        payload={'scope_kind':'business','scope_id':'business-a','action':'sync','request_id':'same'}
        first=client.post('/mobile/outreach',json=payload)
        assert first.status_code==200
        second=client.post('/mobile/outreach',json=payload)
        assert second.json['job']['id']==first.json['job']['id']
        snapshot=client.get('/mobile/outreach?scope_kind=business&scope_id=business-a')
        assert snapshot.status_code==200
        assert snapshot.json['active_job']['id']==first.json['job']['id']
        assert {item['id'] for item in snapshot.json['items']}=={ids['reply-a'],ids['reply-workstream']}
        cursor.execute('SELECT payload_json FROM operator_async_jobs WHERE id=%s',(first.json['job']['id'],))
        assert cursor.fetchone()['payload_json']['sources'][0]['campaign_id']==ids['campaign-a']


def test_postgres_shared_email_recipient_collision_fails_closed(pg,monkeypatch):
    from services import outreach_email_reply_service
    connection,cursor,ids=pg
    for lane in ('a','b'):
        cursor.execute("INSERT INTO outreachsendqueue VALUES(%s,%s,%s,'same@example.test','email')",
            (str(uuid.uuid4()),ids['sender'],ids['touch-'+lane]))
    proxy=Mock();proxy.cursor.return_value=cursor
    monkeypatch.setattr(outreach_email_reply_service,'get_db_connection',lambda:proxy)
    with pytest.raises(outreach_email_reply_service.EmailAdapterError) as error:
        outreach_email_reply_service._assert_campaign_recipient_isolation(ids['sender'],ids['campaign-a'])
    assert error.value.code=='email_reply_cross_business_recipient_ambiguous'
