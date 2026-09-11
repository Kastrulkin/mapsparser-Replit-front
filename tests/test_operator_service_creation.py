import importlib.util
import json
from pathlib import Path
import pytest
from tests.test_operator_voice_pg import pg
from services import operator_service_creation, operator_core, operator_chat_service, operator_audio
from services.operator_google_services import GoogleServices


@pytest.fixture
def creation(pg,monkeypatch):
    conn,c=pg
    c.execute("CREATE TABLE userservices(id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,name TEXT,price TEXT,description TEXT,category TEXT,source TEXT,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ)")
    c.execute("CREATE TABLE journey_actions(id UUID PRIMARY KEY,status TEXT,user_id TEXT,journey_id UUID,business_id TEXT,lead_id TEXT,flow_type TEXT,entity_type TEXT,entity_id TEXT,action_type TEXT,priority INTEGER,due_at TIMESTAMPTZ,title TEXT,description TEXT,cta_label TEXT,cta_target_json JSONB,payload_json JSONB,source_action_id UUID,dedupe_key TEXT,version INTEGER DEFAULT 1,updated_at TIMESTAMPTZ DEFAULT NOW(),created_at TIMESTAMPTZ DEFAULT NOW())")
    c.execute("CREATE UNIQUE INDEX tasks_dedupe ON journey_actions(dedupe_key) WHERE status IN ('ready','in_progress','waiting','blocked')")
    c.execute("CREATE TABLE externalbusinessaccounts(id TEXT,business_id TEXT,source TEXT)")
    c.execute("CREATE TABLE businessmaplinks(business_id TEXT,map_type TEXT,url TEXT)")
    c.execute("CREATE TABLE business_members(business_id TEXT,user_id TEXT,role TEXT,status TEXT)")
    c.execute("ALTER TABLE users ADD COLUMN name TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
    c.execute("ALTER TABLE businesses ADD COLUMN currency TEXT DEFAULT 'EUR'")
    from alembic import op
    monkeypatch.setattr(op,'execute',c.execute)
    path=Path(__file__).parents[1]/'alembic_migrations/versions/20260911_operator_service_creation.py'
    spec=importlib.util.spec_from_file_location('service_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.upgrade();migration.upgrade()
    def auth(cursor,user,business):
        if (user,business)!=('u','b'): raise PermissionError('Нет доступа')
        return {},{}
    monkeypatch.setattr(operator_service_creation,'authorize_actor',auth)
    monkeypatch.setattr(operator_service_creation,'manual_task',lambda *args:(None,'Администратор не настроен.'))
    def disconnected(*args):raise ValueError('Google не подключён.')
    monkeypatch.setattr(operator_service_creation,'load_google',disconnected)
    conn.commit()
    return conn,c


@pytest.mark.parametrize('channel',['telegram','web','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
def test_six_inputs_create_exactly_once(creation,channel,voice):
    conn,c=creation
    message='Добавь услугу Трансфер с детским креслом стоимостью 50 евро'
    payload={'request_id':'request'}
    if voice:
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id='u',business_id='b',channel=channel,conversation_id=None,request_id='recording')
        c.execute("UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    planner=lambda state:{'action':'tool_call','tool':'services.create','arguments':{'name':'Трансфер с детским креслом','price':'50','currency':'EUR'}}
    def router(cursor,**args):return operator_core.route_operator_message(cursor,tool_planner=planner,**args)
    args=dict(business_id='b',user_id='u',channel=channel,message=message,payload=payload,router=router)
    first=operator_chat_service.process_chat(c,**args);conn.commit()
    second=operator_chat_service.process_chat(c,**args)
    assert first['status']=='completed'
    assert first['message_id']==second['message_id']
    c.execute('SELECT * FROM userservices');rows=c.fetchall()
    assert len(rows)==1 and rows[0]['price']=='50' and rows[0]['currency']=='EUR'
    c.execute('SELECT * FROM operator_service_distribution');assert len(c.fetchall())==1


@pytest.mark.parametrize('price',['-1','NaN','Infinity','1.234','1000000001',None])
def test_invalid_price_no_write(creation,price):
    _,c=creation
    outcome=operator_service_creation.create(c,'b','u','Добавь услугу Трансфер','key',{'name':'Трансфер','price':price})
    assert outcome['status']=='clarification_required'
    c.execute('SELECT COUNT(*) n FROM userservices');assert c.fetchone()['n']==0


def test_similar_service_and_foreign_business(creation):
    _,c=creation
    args={'name':'Трансфер','price':'50'}
    operator_service_creation.create(c,'b','u','Добавь услугу Трансфер за 50','one',args)
    outcome=operator_service_creation.create(c,'b','u','Добавь услугу Трансфер за 50','two',args)
    assert outcome['status']=='clarification_required'
    with pytest.raises(PermissionError):operator_service_creation.create(c,'other','u','Добавь услугу Трансфер за 50','one',args)


class Response:
    def __init__(self,data):self.data=data
    def raise_for_status(self):pass
    def json(self):return self.data


class Session:
    def __init__(self):
        self.data={'name':'locations/123','title':'Test','metadata':{'canModifyServiceList':True},'categories':{'primaryCategory':{'name':'gcid:taxi_service'}},'serviceItems':[{'structuredServiceItem':{'serviceTypeId':'old'}}]}
        self.writes=[]
    def get(self,*args,**kwargs):return Response(json.loads(json.dumps(self.data)))
    def patch(self,*args,**kwargs):
        self.writes.append(kwargs);self.data['serviceItems']=kwargs['json']['serviceItems'];return Response(self.data)


def test_google_preserves_previous_and_reconciles_repeat():
    session=Session();client=GoogleServices(session,'accounts/1/locations/123')
    preview=client.preview({'name':'Трансфер','price':'50.25','currency':'EUR'})
    assert not session.writes
    assert client.apply(preview)['verified']
    assert len(session.data['serviceItems'])==2
    assert client.apply(preview)['already_present']
    assert len(session.writes)==1
    assert session.writes[0]['params']=={'updateMask':'serviceItems'}


def test_google_changed_snapshot_blocks_write():
    session=Session();client=GoogleServices(session,'locations/123')
    preview=client.preview({'name':'Трансфер','price':'50','currency':'EUR'})
    session.data['serviceItems'].append({'new':'editor'})
    with pytest.raises(ValueError,match='изменился'):client.apply(preview)
    assert not session.writes


def test_google_ineligible_and_invalid_location():
    session=Session();session.data['metadata']['canModifyServiceList']=False
    with pytest.raises(ValueError):GoogleServices(session,'https://evil/')
    with pytest.raises(ValueError,match='не разрешает'):GoogleServices(session,'locations/123').preview({'name':'Test','price':'1','currency':'EUR'})


def test_create_builds_google_approval_and_stale_local_edit_blocks(creation,monkeypatch):
    conn,c=creation;session=Session()
    monkeypatch.setattr(operator_service_creation,'load_google',lambda *args:(GoogleServices(session,'locations/123'),'account'))
    outcome=operator_service_creation.create(c,'b','u','Добавь услугу Трансфер за 50 евро','key',{'name':'Трансфер','price':'50','currency':'EUR'})
    assert outcome['status']=='approval_required' and not session.writes
    c.execute('UPDATE userservices SET price=60')
    denied=operator_service_creation.apply_google(c,'b','u',outcome['approval']['envelope'])
    assert denied['status']=='blocked' and not session.writes


def test_google_failure_does_not_undo_service(creation,monkeypatch):
    _,c=creation
    def failed(*args):raise TimeoutError()
    monkeypatch.setattr(operator_service_creation,'load_google',failed)
    outcome=operator_service_creation.create(c,'b','u','Добавь услугу Трансфер за 50 евро','key',{'name':'Трансфер','price':'50'})
    assert outcome['status']=='completed' and outcome['google_status']=='blocked'
    c.execute('SELECT COUNT(*) n FROM userservices');assert c.fetchone()['n']==1


def test_manual_task_is_real_scoped_and_deduplicated(creation,monkeypatch):
    _,c=creation
    # Reload only the original function; the creation fixture stubs dispatch.
    spec=importlib.util.spec_from_file_location('manual_services',Path(operator_service_creation.__file__))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    c.execute("INSERT INTO externalbusinessaccounts VALUES ('ya','b','yandex_business')")
    c.execute("INSERT INTO business_members VALUES ('b','u','manager','active')")
    monkeypatch.setenv('JOURNEY_NOTIFICATIONS_ENABLED','false')
    service={'id':'s','name':'Трансфер','price':'50','currency':'EUR'}
    first,text=module.manual_task(c,'b',service)
    second,_=module.manual_task(c,'b',service)
    assert first==second and 'отключены' in text
    c.execute('SELECT * FROM journey_actions');tasks=c.fetchall()
    assert len(tasks)==1 and tasks[0]['user_id']=='u' and tasks[0]['business_id']=='b'
    assert '50 EUR' in tasks[0]['description'] and 'Яндекс' in tasks[0]['description']


def test_confirmation_through_chat_has_correct_capability(creation,monkeypatch):
    conn,c=creation;session=Session()
    monkeypatch.setattr(operator_service_creation,'load_google',lambda *args:(GoogleServices(session,'locations/123'),'account'))
    def planner(state):return {'action':'tool_call','tool':'services.create','arguments':{'name':'Трансфер','price':'50','currency':'EUR'}}
    def router(cursor,**args):return operator_core.route_operator_message(cursor,tool_planner=planner,**args)
    first=operator_chat_service.process_chat(c,business_id='b',user_id='u',channel='web',message='Добавь услугу Трансфер за 50 евро',payload={'request_id':'one'},router=router)
    assert first['capability']=='services.google.add' and first['status']=='approval_required'
    assert first['approval']['status']=='pending'
    c.execute('SELECT capability,envelope_json FROM operatoractions');action=c.fetchone()
    assert action['capability']=='services.google.add'
    outcome,_=operator_core.confirm_pending_operator_action(c,action_id=first['approval']['action_id'],business_id='b',user_id='u')
    assert outcome['google_status']=='completed'
    repeated,replay=operator_core.confirm_pending_operator_action(c,action_id=first['approval']['action_id'],business_id='b',user_id='u')
    assert repeated['google_status']=='completed' and replay
    assert len(session.writes)==1


def test_existing_selection_previews_then_updates_without_duplicate(creation):
    _,c=creation
    created=operator_service_creation.create(c,'b','u','Добавь услугу Трансфер за 50 евро','one',{'name':'Трансфер','price':'50'})
    preview=operator_service_creation.existing_price(c,'b','u','Измени существующую услугу на 60',{'service_id':created['service_id'],'price':'60'})
    assert preview['status']=='approval_required'
    outcome=operator_service_creation.apply_existing_price(c,'b','u',preview['approval']['envelope'])
    assert outcome['status']=='completed'
    c.execute('SELECT price FROM userservices');rows=c.fetchall()
    assert len(rows)==1 and rows[0]['price']=='60'


def test_expired_and_foreign_confirmation_do_not_write(creation,monkeypatch):
    _,c=creation;session=Session()
    monkeypatch.setattr(operator_service_creation,'load_google',lambda *args:(GoogleServices(session,'locations/123'),'account'))
    planner=lambda state:{'action':'tool_call','tool':'services.create','arguments':{'name':'Трансфер','price':'50'}}
    def router(cursor,**args):return operator_core.route_operator_message(cursor,tool_planner=planner,**args)
    first=operator_chat_service.process_chat(c,business_id='b',user_id='u',channel='web',message='Добавь услугу Трансфер за 50',router=router)
    ident=first['approval']['action_id']
    denied,_=operator_core.confirm_pending_operator_action(c,action_id=ident,business_id='foreign',user_id='u')
    assert denied['status']=='blocked'
    c.execute("UPDATE operatoractions SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s",(ident,))
    denied,_=operator_core.confirm_pending_operator_action(c,action_id=ident,business_id='b',user_id='u')
    assert denied['blocked_reasons']==['approval_expired'] and not session.writes


def test_notifications_require_preference_and_current_membership(creation,monkeypatch):
    conn,c=creation
    from services import journey_action_notifications
    monkeypatch.setenv('JOURNEY_NOTIFICATIONS_ENABLED','true')
    c.execute('CREATE TABLE telegramcontrolpreferences(user_id TEXT,telegram_id TEXT,notification_preferences_json JSONB)')
    c.execute('CREATE TABLE journey_action_notification_deliveries(dedupe_key TEXT PRIMARY KEY,action_id UUID,action_version INTEGER,user_id TEXT,telegram_id TEXT,message_text TEXT,reply_markup_json JSONB,sent_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())')
    c.execute("INSERT INTO business_members VALUES ('b','u','manager','active')")
    c.execute("INSERT INTO telegramcontrolpreferences VALUES ('u','123','{\"business:b\":{\"tasks\":true}}')")
    c.execute("INSERT INTO journey_actions(id,business_id,user_id,entity_type,status,title,description,cta_label,due_at,priority) VALUES ('00000000-0000-0000-0000-000000000001','b','u','service','ready','Обновить услугу','50 EUR, Яндекс','Сделать',NOW(),100)")
    deliveries=journey_action_notifications.collect_due_journey_action_notifications(conn)
    assert len(deliveries)==1 and deliveries[0]['telegram_id']=='123'
    assert len(journey_action_notifications.collect_due_journey_action_notifications(conn))==1
    c.execute("UPDATE business_members SET status='revoked'")
    assert journey_action_notifications.collect_due_journey_action_notifications(conn)==[]


def test_google_omitted_defaults_are_verified():
    session=Session();client=GoogleServices(session,'locations/123')
    preview=client.preview({'name':'Трансфер','price':'50','currency':'EUR'})
    client.apply(preview)
    session.data['serviceItems'][-1]['price'].pop('nanos')
    session.data['serviceItems'][-1]['freeFormServiceItem']['label']['languageCode']='ru'
    assert client.apply(preview)['already_present']
    assert len(session.writes)==1


@pytest.mark.parametrize('message',['Подготовь пост про новую услугу','Измени тему поста на новую услугу','Добавь в контент-план пост про новую услугу'])
def test_service_route_does_not_steal_content_requests(message):
    assert not operator_service_creation.service_input(message)


def test_negative_instruction_never_creates(creation):
    _,c=creation
    outcome=operator_service_creation.create(c,'b','u','Пожалуйста не добавляй услугу Трансфер за 50 евро','negative',{'name':'Трансфер','price':'50','currency':'EUR'})
    assert outcome['status']=='clarification_required'
    c.execute('SELECT COUNT(*) n FROM userservices');assert c.fetchone()['n']==0
