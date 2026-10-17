"""Real local PostgreSQL; bot transports captured, no model/provider requests."""
import base64
import json
import os
import uuid
from types import SimpleNamespace

import pytest
import psycopg2

from tests.test_max_control_pg import max_pg
from tests.test_max_owner_dialogues import dialogues, bind
from services import operator_work_handoff, operator_editorial, max_owner_dialogues
from services.operator_conversations import find_latest_operator_conversation
from services.operator_audio import authorize_actor
from subscription_manager import capability_access_payload


@pytest.fixture(scope='module')
def postgres_container():
    dsn = os.getenv('CLIENT_WORK_TEST_DSN', '')
    if not dsn:
        pytest.skip('CLIENT_WORK_TEST_DSN: disposable loopback database required')
    config = psycopg2.extensions.parse_dsn(dsn)
    if config.get('host') != '127.0.0.1' or 'test' not in config.get('dbname', '') or config.get('hostaddr') or config.get('service'):
        raise RuntimeError('Refusing a non-test PostgreSQL destination')
    return SimpleNamespace(get_connection_url=lambda: dsn)


@pytest.fixture
def prepared(dialogues, monkeypatch):
    bind(dialogues)
    conn = dialogues[0]
    cursor = conn.cursor()
    cursor.execute('ALTER TABLE users ADD COLUMN telegram_id TEXT')
    cursor.execute("UPDATE users SET telegram_id='999' WHERE id='u1'")
    cursor.execute('''CREATE TABLE operatorconversations(id TEXT PRIMARY KEY,business_id TEXT,user_id TEXT,
        channel TEXT,transport_key TEXT,status TEXT DEFAULT 'active',pending_context JSONB DEFAULT '{}',
        input_context_json JSONB DEFAULT '{}',updated_at TIMESTAMPTZ DEFAULT NOW())''')
    item = str(uuid.uuid4())
    row = {'id':item,'plan_id':'plan','theme':'Реальный пост','plan_status':'active','updated_at':'2026-10-16T00:00:00+00:00'}
    def items(c, business, **kwargs):
        return [row] if business == 'b1' and kwargs.get('item_id') == item else []
    monkeypatch.setattr(operator_editorial, '_items', items)
    monkeypatch.setenv('MAX_BOT_USERNAME','test_localos_bot')
    conn.commit()
    return dialogues, item, row


@pytest.mark.parametrize('platform,channel', [('telegram','telegram'),('max','max_bot')])
def test_prepare_is_durable_but_only_explicit_resume_activates_selection(prepared, platform, channel):
    fixtures, item, row = prepared
    conn, connect, _, _ = fixtures
    result = operator_work_handoff.prepare_handoff(conn.cursor(),user_id='u1',business_id='b1',platform=platform,item_id=item,request_id=str(uuid.uuid4()))
    conn.commit()
    fresh = connect()
    c = fresh.cursor()
    assert find_latest_operator_conversation(c,business_id='b1',user_id='u1',channel=channel) == {}
    token = result['url'].split('start=')[1]
    resumed = operator_work_handoff.resume_handoff(c,user_id='u1',platform=platform,token=token)
    fresh.commit()
    active = find_latest_operator_conversation(c,business_id='b1',user_id='u1',channel=channel)
    assert active['id'] == resumed['conversation_id']
    assert active['pending_context']['selected_item']['item_id'] == item
    assert active['pending_context']['selected_item']['version'] == operator_editorial._version(row)
    assert '/' + platform + '/control?' in resumed['return_url']
    fresh.close()


@pytest.mark.parametrize('platform', ['telegram', 'max'])
def test_content_pilot_keeps_trial_and_rechecks_revocation(prepared, monkeypatch, platform):
    import subscription_manager
    from services import operator_audio
    fixtures, item, _ = prepared
    conn = fixtures[0]
    c = conn.cursor()
    c.execute('ALTER TABLE businesses ADD COLUMN subscription_tier TEXT, ADD COLUMN subscription_status TEXT, ADD COLUMN subscription_ends_at TIMESTAMPTZ')
    monkeypatch.setattr(operator_audio, 'authorize_actor', authorize_actor)
    monkeypatch.setattr(subscription_manager, 'capability_access_payload', capability_access_payload)
    c.execute("UPDATE businesses SET subscription_tier='trial',subscription_status='active' WHERE id='b1'")
    conn.commit()
    monkeypatch.setenv('CONTENT_ACCESS_BUSINESS_IDS', 'b1')
    result = operator_work_handoff.prepare_handoff(c, user_id='u1', business_id='b1', platform=platform, item_id=item, request_id=str(uuid.uuid4()))
    conn.commit()
    c.execute("SELECT subscription_tier FROM businesses WHERE id='b1'")
    assert c.fetchone()['subscription_tier'] == 'trial'
    monkeypatch.setenv('CONTENT_ACCESS_BUSINESS_IDS', '')
    with pytest.raises(PermissionError):
        operator_work_handoff.resume_handoff(c, user_id='u1', platform=platform, token=result['url'].split('start=')[1])
    conn.rollback()


def test_actual_max_start_handler_restores_selection_and_returns_max_app_link(prepared):
    fixtures,item,_ = prepared
    conn = fixtures[0]
    result = operator_work_handoff.prepare_handoff(conn.cursor(),user_id='u1',business_id='b1',platform='max',item_id=item,request_id=str(uuid.uuid4()))
    conn.commit()
    payload = {'update_type':'bot_started','payload':result['url'].split('start=')[1],'user':{'user_id':123},'chat_id':123}
    reply = max_owner_dialogues.prepare_owner_dialogue(conn.cursor(),payload,'start-work-event','123')
    conn.commit()
    assert 'обсуждение выбранного поста' in reply['text']
    buttons = [button for message in reply['messages'] for attachment in message.get('attachments',[]) for row in attachment['payload']['buttons'] for button in row]
    url = next(button['url'] for button in buttons if button['text']=='Вернуться к посту')
    assert url.startswith('https://max.ru/test_localos_bot?startapp=nav_')
    encoded = url.split('nav_')[1]
    nav = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
    assert nav == {'screen':'content','scope_type':'business','scope_id':'b1','item_type':'content_item','item_id':item}


def test_revoked_access_and_wrong_platform_cannot_resume_a_prepared_link(prepared):
    fixtures,item,_ = prepared
    conn = fixtures[0]
    result = operator_work_handoff.prepare_handoff(conn.cursor(),user_id='u1',business_id='b1',platform='max',item_id=item,request_id=str(uuid.uuid4()))
    conn.commit()
    token=result['url'].split('start=')[1]
    with pytest.raises(PermissionError): operator_work_handoff.resume_handoff(conn.cursor(),user_id='u1',platform='telegram',token=token)
    conn.rollback()
    conn.cursor().execute("UPDATE businesses SET owner_id='u2' WHERE id='b1'")
    conn.commit()
    with pytest.raises(PermissionError): operator_work_handoff.resume_handoff(conn.cursor(),user_id='u1',platform='max',token=token)
    conn.rollback()


@pytest.mark.parametrize('channel,platform', [('telegram_mini_app','telegram'),('max_mini_app','max')])
def test_mobile_chat_passes_the_verified_post_to_the_existing_router(prepared, monkeypatch, channel, platform):
    from services import operator_chat_service, operator_workday, operator_followups
    fixtures,item,row=prepared
    conn=fixtures[0]
    c=conn.cursor()
    c.execute('''CREATE TABLE operatormessages(id TEXT PRIMARY KEY,conversation_id TEXT,business_id TEXT,user_id TEXT,
        role TEXT,content TEXT,capability TEXT,status TEXT,result_json JSONB,created_at TIMESTAMPTZ)''')
    monkeypatch.setattr(operator_workday,'enabled',lambda business:False)
    monkeypatch.setattr(operator_chat_service,'list_pending_operator_actions',lambda *a,**kw:[])
    monkeypatch.setattr(operator_followups,'remember_selection',lambda *a,**kw:None)
    captured=[]
    def router(cursor,**kwargs):
        captured.append(kwargs['pending_context'])
        return {'status':'completed','chat_response':'Пост выбран.'},kwargs['pending_context']
    result=operator_chat_service._process_chat(c,business_id='b1',user_id='u1',channel=channel,message='Сделай текст короче',
        router=router,payload={'selected_object':{'type':'content_item','id':item,'updated_at':'2026-10-16T00:00:00+00:00'}})
    assert captured[0]['selected_item']['item_id']==item
    assert captured[0]['selected_item']['version']==operator_editorial._version(row)
    assert '/' + platform + '/control?' in result['work_return_url']
    c.execute('SELECT COUNT(*) AS n FROM operatormessages')
    assert c.fetchone()['n']==2
    conn.commit()


@pytest.mark.parametrize('platform', ['telegram','max'])
def test_handoff_http_endpoint_commits_only_prepared_navigation(prepared, monkeypatch, platform):
    from flask import Flask
    from api import operator_api
    fixtures,item,_=prepared
    _,connect,_,_=fixtures
    class Database:
        def __init__(self): self.conn=connect()
        def close(self): self.conn.close()
    monkeypatch.setattr(operator_api,'DatabaseManager',Database)
    monkeypatch.setattr(operator_api,'require_auth_from_request',lambda:{'user_id':'u1'})
    app=Flask(__name__);app.register_blueprint(operator_api.operator_bp)
    response=app.test_client().post('/api/operator/work-handoff',json={'business_id':'b1','item_id':item,'request_id':str(uuid.uuid4()),'platform':platform})
    assert response.status_code==200
    connection=connect();c=connection.cursor()
    c.execute('SELECT status,pending_context FROM operatorconversations')
    rows=c.fetchall()
    assert len(rows)==1 and rows[0]['status']=='handoff_prepared'
    assert rows[0]['pending_context']['selected_item']['item_id']==item
    connection.close()


@pytest.mark.parametrize('platform', ['telegram','max'])
def test_client_content_entry_selects_only_authorized_business_without_execution(prepared, platform):
    import asyncio
    fixtures,_,_=prepared
    conn,_,host,selection=fixtures
    business=str(uuid.uuid4())
    conn.cursor().execute("INSERT INTO businesses(id,owner_id,name) VALUES (%s,'u1','Мелиора — тестовый вход')",(business,))
    conn.commit()
    selection['scope']={'kind':'business','id':business,'name':'Мелиора — тестовый вход','business_ids':[business]}
    token='content_'+uuid.UUID(business).hex
    if platform=='max':
        reply=max_owner_dialogues.prepare_owner_dialogue(conn.cursor(),{'update_type':'bot_started','payload':token,'user':{'user_id':123},'chat_id':123},'entry-work-event','123')
        assert 'Откройте контент-план' in reply['text']
        urls=[button['url'] for message in reply['messages'] for attachment in message.get('attachments',[]) for row in attachment['payload']['buttons'] for button in row if button.get('url')]
        assert any(url.startswith('https://max.ru/test_localos_bot?startapp=nav_') for url in urls)
    else:
        replies=[]
        class Message:
            async def reply_text(self,text,**kwargs): replies.append((text,kwargs))
        message=Message()
        update=SimpleNamespace(effective_user=SimpleNamespace(id=999),effective_message=message,message=message)
        asyncio.run(host.start(update,SimpleNamespace(args=[token])))
        assert 'Откройте контент-план' in replies[0][0]
        assert '/telegram/control?' in replies[0][1]['reply_markup'].inline_keyboard[0][0].web_app.url
    c=conn.cursor();c.execute('SELECT COUNT(*) AS n FROM operatorconversations')
    assert c.fetchone()['n']==0
