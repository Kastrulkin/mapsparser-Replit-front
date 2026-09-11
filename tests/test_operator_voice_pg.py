"""Real PostgreSQL: isolated schema, real journals, stubbed domain executor/STT.
Run with OPERATOR_VOICE_TEST_DSN pointing ONLY to a disposable test database.
"""
import importlib.util
import os
import uuid
from pathlib import Path
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from services import operator_chat_service, operator_audio


@pytest.fixture
def pg(monkeypatch,tmp_path):
    dsn=os.getenv('OPERATOR_VOICE_TEST_DSN')
    if not dsn: pytest.skip('OPERATOR_VOICE_TEST_DSN not configured')
    conn=psycopg2.connect(dsn,cursor_factory=RealDictCursor)
    schema='voice_'+uuid.uuid4().hex
    cursor=conn.cursor(); cursor.execute('CREATE SCHEMA '+schema); cursor.execute('SET search_path TO '+schema)
    cursor.execute('CREATE TABLE users (id TEXT PRIMARY KEY)'); cursor.execute('CREATE TABLE businesses (id TEXT PRIMARY KEY)')
    cursor.execute("INSERT INTO users VALUES ('u')");cursor.execute("INSERT INTO businesses VALUES ('b')")
    from alembic import op
    monkeypatch.setattr(op,'execute',cursor.execute)
    for name in ['20260711_add_operator_conversations.py','20260727_add_operator_async_jobs.py','20260910_operator_audio.py']:
        path=Path(__file__).parents[1]/'alembic_migrations/versions'/name
        spec=importlib.util.spec_from_file_location('voice_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.upgrade()
        module.upgrade()  # Idempotent application.
    cursor.execute('ALTER TABLE operator_async_jobs ADD COLUMN lease_token TEXT')
    monkeypatch.setattr(operator_audio,'authorize_actor',lambda *a:({'role':'business_owner'},{'active':True}))
    monkeypatch.setenv('OPERATOR_VOICE_INPUT_ENABLED','true');monkeypatch.setenv('OPERATOR_VOICE_OUTPUT_ENABLED','true')
    monkeypatch.setenv('OPERATOR_VOICE_BUSINESS_IDS','b');monkeypatch.setenv('OPERATOR_AUDIO_DIR',str(tmp_path))
    conn.commit()
    yield conn,cursor
    conn.rollback();cursor.execute('DROP SCHEMA '+schema+' CASCADE');conn.commit();conn.close()


COMMANDS=['Что ты умеешь?','Покажи отзывы без ответа','Подготовь ответы на отзывы','Подготовь пост про нового мастера','Обнови карточку','Измени цену услуги','Неизвестная команда']
from services.operator_core import operator_capability_catalog
COMMANDS = list(dict.fromkeys(COMMANDS + [entry['examples'][0] for entry in operator_capability_catalog() if entry.get('examples')]))
@pytest.mark.parametrize('channel',['web','telegram_mini_app','telegram'])
@pytest.mark.parametrize('voice',[False,True])
@pytest.mark.parametrize('command',COMMANDS)
def test_six_inputs_preserve_context_and_deduplicate(pg,channel,voice,command):
    conn,cursor=pg;calls=[];payload={'request_id':'request-1'}
    if voice:
        audio=operator_audio.create_transcription(cursor,content=b'fake provider input',user_id='u',business_id='b',channel=channel,conversation_id=None,request_id='recording-1')
        cursor.execute("UPDATE operator_audio_assets SET status='ready',transcript=%s,path=NULL WHERE id=%s",(command,audio['asset_id']))
        cursor.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(audio['job_id'],))
        payload.update(transcription_id=audio['asset_id'],conversation_id=audio['conversation_id'])
    def router(cursor,**kwargs):
        calls.append(kwargs)
        return {'status':'clarification_required','chat_response':'Уточните услугу','capability':'test'}, {'service':'pending'}
    args=dict(business_id='b',user_id='u',channel=channel,message=command,payload=payload,router=router)
    first=operator_chat_service.process_chat(cursor,**args);conn.commit()
    duplicate=operator_chat_service.process_chat(cursor,**args)
    assert duplicate['message_id']==first['message_id'];assert len(calls)==1
    assert calls[0]['message']==command
    next_result=operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel=channel,message='Стрижка',payload={'request_id':'request-2'},router=router)
    assert next_result['conversation_id']==first['conversation_id']
    assert calls[1]['pending_context']=={'service':'pending'}
    cursor.execute('SELECT COUNT(*) n FROM operatormessages');assert cursor.fetchone()['n']==4
    with pytest.raises(ValueError):
        operator_chat_service.process_chat(cursor,**{**args,'message':'Другая команда'})


def test_channels_are_separate_and_foreign_id_is_denied(pg):
    _,cursor=pg
    def router(*a,**k):return {'status':'completed','chat_response':'ok'},{}
    ids=[]
    for channel in ['web','telegram','telegram_mini_app']:
        result=operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel=channel,message='hello',router=router)
        ids.append(result['conversation_id'])
    assert len(set(ids))==3
    with pytest.raises(ValueError): operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel='web',message='hello',payload={'conversation_id':ids[1]},router=router)


def test_quota_and_single_submission(pg):
    _,cursor=pg
    for index in range(20):
        operator_audio.create_transcription(cursor,content=b'input',user_id='u',business_id='b',channel='web',conversation_id=None,request_id=str(index))
    with pytest.raises(ValueError,match='лимит'):
        operator_audio.create_transcription(cursor,content=b'input',user_id='u',business_id='b',channel='web',conversation_id=None,request_id='21')


def test_worker_stt_tts_and_restart_resume(pg,monkeypatch):
    conn,cursor=pg
    from services import operator_async_jobs, operator_speechkit
    import database_manager
    schema=cursor.connection.get_dsn_parameters().get('options','')
    cursor.execute('SELECT current_schema() schema'); schema=cursor.fetchone()['schema']
    class DB:
        def __init__(self):
            self.conn=psycopg2.connect(os.environ['OPERATOR_VOICE_TEST_DSN'],cursor_factory=RealDictCursor)
            self.conn.cursor().execute('SET search_path TO '+schema)
        def close(self): self.conn.close()
    monkeypatch.setattr(database_manager,'DatabaseManager',DB)
    monkeypatch.setattr(operator_audio,'normalize_audio',lambda path,target:(target.write_bytes(b'normalized') and 2))
    calls=[]
    class Provider:
        def start(self,content):calls.append('start');return 'operation-1'
        def result(self,operation):return 'Подготовь пост'
        def synthesize(self,text):calls.append('tts');return b'ogg bytes'
    monkeypatch.setattr(operator_speechkit,'SpeechKit',Provider)
    upload=operator_audio.create_transcription(cursor,content=b'voice',user_id='u',business_id='b',channel='telegram',conversation_id=None,request_id='recording')
    conn.commit()
    finished=operator_async_jobs.process_next_operator_async_job()
    assert finished['status']=='completed';assert finished['result']['transcript']=='Подготовь пост'
    cursor.execute('SELECT path,transcript,status FROM operator_audio_assets WHERE id=%s',(upload['asset_id'],))
    assert cursor.fetchone()=={'path':None,'transcript':'Подготовь пост','status':'ready'}
    def router(*a,**k):return {'status':'completed','chat_response':'Черновик готов'},{}
    reply=operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel='telegram',message='Подготовь пост',router=router,
        payload={'request_id':'r','transcription_id':upload['asset_id'],'conversation_id':upload['conversation_id']})
    speech=operator_audio.create_speech(cursor,user_id='u',message_id=reply['message_id']);conn.commit()
    finished=operator_async_jobs.process_next_operator_async_job()
    assert finished['status']=='completed';assert finished['result']['audio_url'].endswith(speech['asset_id'])
    cached=operator_audio.create_speech(cursor,user_id='u',message_id=reply['message_id'])
    assert cached['job_id']==speech['job_id'];assert calls==['start','tts']


def test_concurrent_retry_runs_domain_once(pg):
    conn,cursor=pg
    from concurrent.futures import ThreadPoolExecutor
    import time
    cursor.execute('SELECT current_schema() schema');schema=cursor.fetchone()['schema'];conn.commit()
    calls=[]
    def router(*args,**kwargs):
        calls.append(1);time.sleep(0.03)
        return {'status':'completed','chat_response':'Одна задача'},{}
    def send():
        connection=psycopg2.connect(os.environ['OPERATOR_VOICE_TEST_DSN'],cursor_factory=RealDictCursor)
        try:
            current=connection.cursor();current.execute('SET search_path TO '+schema)
            result=operator_chat_service.process_chat(current,business_id='b',user_id='u',channel='web',message='Обнови карточку',payload={'request_id':'same'},router=router)
            connection.commit();return result['message_id']
        finally:connection.close()
    pool=ThreadPoolExecutor(max_workers=2)
    try: results=list(pool.map(lambda _:send(),range(2)))
    finally:pool.shutdown()
    assert results[0]==results[1];assert calls==[1]


def test_asset_isolation_expiry_and_cancel_api(pg,monkeypatch):
    conn,cursor=pg
    from flask import Flask,Blueprint
    from api import operator_audio_api
    cursor.execute('SELECT current_schema() schema');schema=cursor.fetchone()['schema']
    class DB:
        def __init__(self):
            self.conn=psycopg2.connect(os.environ['OPERATOR_VOICE_TEST_DSN'],cursor_factory=RealDictCursor)
            self.conn.cursor().execute('SET search_path TO '+schema)
        def close(self):self.conn.close()
    monkeypatch.setattr(operator_audio_api,'DatabaseManager',DB)
    monkeypatch.setattr(operator_audio_api,'require_auth_from_request',lambda:{'user_id':'u'})
    monkeypatch.setattr(operator_audio_api,'verify_business_access',lambda *args:(True,'u'))
    # The API imported the authorization function by name; use a valid session boundary for this fixture.
    monkeypatch.setattr(operator_audio_api,'authorize_actor',lambda *args:({},{}))
    app=Flask(__name__);bp=Blueprint('voice_test',__name__,url_prefix='/api/operator');operator_audio_api.register_audio_routes(bp);app.register_blueprint(bp)
    audio=operator_audio.create_transcription(cursor,content=b'input',user_id='u',business_id='b',channel='web',conversation_id=None,request_id='one');conn.commit()
    client=app.test_client()
    assert client.get('/api/operator/audio/'+audio['asset_id']).status_code==400 # Never serves raw input.
    assert client.post('/api/operator/audio/'+audio['asset_id']+'/cancel').status_code==200
    cursor.execute('SELECT status FROM operator_async_jobs WHERE id=%s',(audio['job_id'],));assert cursor.fetchone()['status']=='cancelled'
    with pytest.raises(PermissionError):operator_audio.load_asset(cursor,audio['asset_id'],'different-user')
    with pytest.raises(PermissionError):operator_audio.load_asset(cursor,audio['asset_id'],'u','different-business')
    cursor.execute("UPDATE operator_audio_assets SET expires_at=NOW()-INTERVAL '1 minute' WHERE id=%s",(audio['asset_id'],));conn.commit()
    assert client.get('/api/operator/audio/'+audio['asset_id']).status_code==403


def test_real_actor_membership_and_revocation(pg,monkeypatch):
    _,cursor=pg
    # Restore the implementation from the module without disturbing the fixture's stub.
    import importlib.util
    path=Path(__file__).parents[1]/'src/services/operator_audio.py'
    spec=importlib.util.spec_from_file_location('voice_auth_under_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cursor.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE')
    cursor.execute("ALTER TABLE businesses ADD COLUMN owner_id TEXT DEFAULT 'u', ADD COLUMN network_id TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN subscription_tier TEXT DEFAULT 'concierge', ADD COLUMN subscription_status TEXT DEFAULT 'active', ADD COLUMN subscription_ends_at TIMESTAMPTZ")
    cursor.execute('CREATE TABLE networks (id TEXT,owner_id TEXT)')
    cursor.execute('CREATE TABLE business_members (business_id TEXT,user_id TEXT,status TEXT)')
    cursor.execute('CREATE TABLE network_members (network_id TEXT,user_id TEXT,status TEXT)')
    cursor.execute("INSERT INTO users(id) VALUES ('employee'),('outsider')")
    cursor.execute("INSERT INTO business_members VALUES ('b','employee','active')")
    actor,access=module.authorize_actor(cursor,'employee','b')
    assert actor['role']=='business_user';assert 'maps.reviews' in access['capabilities']
    with pytest.raises(PermissionError):module.authorize_actor(cursor,'outsider','b')
    cursor.execute("UPDATE business_members SET status='revoked'")
    with pytest.raises(PermissionError):module.authorize_actor(cursor,'employee','b')
    cursor.execute("UPDATE users SET is_active=FALSE WHERE id='u'")
    with pytest.raises(PermissionError):module.authorize_actor(cursor,'u','b')


def test_changed_preview_and_expired_approval_cannot_execute(pg):
    _,cursor=pg
    from services.operator_core import confirm_pending_operator_action
    def router(cursor,**kwargs):
        return {'status':'approval_required','capability':'services.price.update','chat_response':'Проверьте цену',
                'approval':{'envelope':{'price':kwargs['message']}}},{}
    first=operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel='web',message='1500',payload={'request_id':'p1'},router=router)
    second=operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel='web',message='2000',payload={'request_id':'p2'},router=router)
    old,_=confirm_pending_operator_action(cursor,action_id=first['approval']['action_id'],business_id='b',user_id='u')
    assert old['blocked_reasons']==['action_not_pending']
    cursor.execute("UPDATE operatoractions SET expires_at=NOW()-INTERVAL '1 minute' WHERE id=%s",(second['approval']['action_id'],))
    expired,_=confirm_pending_operator_action(cursor,action_id=second['approval']['action_id'],business_id='b',user_id='u')
    assert expired['blocked_reasons']==['approval_expired']
    renewed=operator_chat_service.process_chat(cursor,business_id='b',user_id='u',channel='web',message='2000',payload={'request_id':'p3'},router=router)
    assert renewed['approval']['action_id'] != second['approval']['action_id']
