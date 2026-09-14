import importlib.util
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import operator_workday, operator_attachments, operator_workday_router, operator_colleagues, yandex_disk
from services.operator_conversations import get_or_create_operator_conversation


@pytest.fixture
def workday(journal,monkeypatch):
    conn,c=journal
    c.execute('ALTER TABLE users ADD COLUMN name TEXT, ADD COLUMN telegram_id TEXT')
    c.execute("UPDATE users SET name=id,telegram_id='123' WHERE id='u'")
    c.execute("ALTER TABLE businesses ADD COLUMN owner_id TEXT DEFAULT 'u'")
    c.execute('''CREATE TABLE journey_actions(id UUID PRIMARY KEY,business_id TEXT,user_id TEXT,flow_type TEXT,
        entity_type TEXT,entity_id TEXT,action_type TEXT,title TEXT,description TEXT,cta_label TEXT,cta_target_json JSONB,payload_json JSONB,dedupe_key TEXT UNIQUE,due_at TIMESTAMPTZ)''')
    c.execute('''CREATE TABLE journey_action_notification_deliveries(dedupe_key TEXT PRIMARY KEY,action_id UUID,
        action_version INTEGER,user_id TEXT,telegram_id TEXT,message_text TEXT,reply_markup_json JSONB,sent_at TIMESTAMPTZ)''')
    from alembic import op
    monkeypatch.setattr(op,'execute',c.execute)
    spec=importlib.util.spec_from_file_location('workday_migration',Path(__file__).parents[1]/'alembic_migrations/versions/20260914_operator_workday.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.upgrade();migration.upgrade()
    monkeypatch.setenv('OPERATOR_WORKDAY_BUSINESS_IDS','b')
    return conn,c


def entries():
    return [{'time':'10:00','service_name':'Окрашивание','master':'Первый','duration_minutes':60},
            {'time':'11:30','service_name':'Окрашивание','master':'Первый','duration_minutes':60}]


def prepare(c,version=0,rows=None):
    return operator_workday.prepare(c,'b','admin',{'date':'2026-09-14','version':version,'entries':rows if rows is not None else entries()},
        {'message':'Сохрани расписание дня','attachment_ids':[]})['approval']['envelope']


def test_schedule_preview_apply_replay_and_no_bookings(workday):
    conn,c=workday
    c.execute('SELECT COUNT(*) n FROM bookings');before=c.fetchone()['n']
    proposal=prepare(c)
    assert operator_workday.schedule(c,'b','2026-09-14')=={}
    saved=operator_workday.apply(c,'b','admin',proposal,'first')
    assert saved['schedule']['version']==1
    assert operator_workday.apply(c,'b','admin',proposal,'first')['idempotent']
    assert operator_workday.apply(c,'b','admin',proposal,'second')['status']=='blocked'
    c.execute('SELECT COUNT(*) n FROM bookings');assert c.fetchone()['n']==before
    c.execute('SELECT COUNT(*) n FROM financialtransactions');assert c.fetchone()['n']==0


def test_ambiguous_service_and_invalid_time(workday):
    _,c=workday
    with pytest.raises(ValueError):prepare(c,rows=[{'time':'25:00','service_name':'Окрашивание'}])
    c.execute("INSERT INTO userservices VALUES ('other','b','Окрашивание',TRUE,'100',60)")
    with pytest.raises(ValueError,match='Уточните услугу'):prepare(c)


def test_briefing_gap_and_unknown_time(workday):
    _,c=workday
    operator_workday.apply(c,'b','admin',prepare(c),'first')
    result=operator_workday.briefing(c,'b','admin',{'date':'2026-09-14'})
    assert result['items'][0]['recommendations'][0]['time_verified']
    assert not result['items'][1]['recommendations'][0]['time_verified']
    assert 'Нужно проверить свободное время' in result['chat_response']


def test_scope_revoked_and_pilot_off(workday,monkeypatch):
    _,c=workday
    with pytest.raises(PermissionError):operator_workday.briefing(c,'other','admin',{'date':'2026-09-14'})
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='admin'")
    with pytest.raises(PermissionError):prepare(c)
    monkeypatch.setenv('OPERATOR_WORKDAY_BUSINESS_IDS','')
    with pytest.raises(PermissionError):operator_workday.briefing(c,'b','u',{'date':'2026-09-14'})


def test_attachment_replay_and_isolation(workday):
    _,c=workday
    data=b'time;service\n10:00;test'
    item=operator_attachments.receive(c,business_id='b',user_id='admin',channel='web',content=data,name='day.csv',mime_type='text/csv',request_key='file')
    replay=operator_attachments.receive(c,business_id='b',user_id='admin',channel='web',content=data,name='day.csv',mime_type='text/csv',request_key='file')
    assert replay['id']==item['id'] and not item['photo_asset_id']
    with pytest.raises(PermissionError):operator_attachments.load(c,'b','master',item['id'])
    with pytest.raises(ValueError):operator_attachments.receive(c,business_id='b',user_id='admin',channel='web',content=b'changed',name='day.csv',mime_type='text/csv',request_key='file')
    extracted=operator_attachments.classify(c,'b','admin',item['id'],'schedule',item['conversation_id'])
    assert extracted['source_text']==data.decode()
    with pytest.raises(ValueError):operator_attachments.classify(c,'b','admin',item['id'],'content',item['conversation_id'])


def test_context_refs_require_same_user_conversation(workday):
    _,c=workday
    item=operator_attachments.receive(c,business_id='b',user_id='admin',channel='web',content=b'a,b',name='day.csv',mime_type='text/csv',request_key='file')
    selected=operator_workday_router.input_context(c,'b','admin',item['conversation_id'],{'attachment_ids':[item['id']]})
    assert selected['attachments'][0]['purpose']=='unknown'
    other=get_or_create_operator_conversation(c,business_id='b',user_id='admin',channel='telegram',transport_key='tg')
    with pytest.raises(PermissionError):operator_workday_router.input_context(c,'b','admin',other['id'],{'attachment_ids':[item['id']]})


def test_recipient_and_schedule_versions_checked(workday):
    _,c=workday
    operator_workday.apply(c,'b','admin',prepare(c),'schedule')
    args={'date':'2026-09-14','schedule_version':1,'message':'Предложите уход при наличии времени.'}
    with pytest.raises(ValueError,match='получателя'):operator_colleagues.prepare(c,'b','admin',args)
    c.execute("INSERT INTO operator_pilot_settings(business_id,recipient_user_id,updated_by) VALUES ('b','u','u')")
    preview=operator_colleagues.prepare(c,'b','admin',args)['approval']['envelope']
    c.execute("UPDATE operator_pilot_settings SET version=2 WHERE business_id='b'")
    with pytest.raises(ValueError,match='Получатель изменился'):operator_colleagues.enqueue(c,'b','admin',preview,'send')
    c.execute('SELECT COUNT(*) n FROM journey_action_notification_deliveries');assert c.fetchone()['n']==0


@pytest.mark.parametrize('url',['http://up.yandex.net/file','https://evil.test/','https://yandex.net.evil.test/','https://user:pass@up.yandex.net/file'])
def test_disk_rejects_untrusted_upload_destination(url):
    with pytest.raises(ValueError):yandex_disk.provider_href(url)


def test_disk_accepts_provider_destination():
    assert yandex_disk.provider_href('https://uploader.yandex.net/file')=='https://uploader.yandex.net/file'


def test_known_gap_only():
    rows=entries()
    assert operator_workday.free_minutes(rows[0],rows)==30
    assert operator_workday.free_minutes(rows[1],rows) is None
    assert operator_workday.free_minutes({**rows[0],'master':''},rows) is None


def test_manager_execution_rights_are_capability_and_pilot_scoped(workday,monkeypatch):
    from core.action_policy import check_tenant_access
    _,c=workday
    assert check_tenant_access(c,'b','admin',False,'work.colleague.send')['ok']
    assert check_tenant_access(c,'b','admin',False,'finance.daily.apply_operator')['ok']
    assert not check_tenant_access(c,'b','admin',False,'social.publish')['ok']
    assert not check_tenant_access(c,'b','admin',False)['ok']
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='admin'")
    assert not check_tenant_access(c,'b','admin',False,'work.colleague.send')['ok']
    c.execute("UPDATE business_members SET status='active' WHERE user_id='admin'")
    monkeypatch.setenv('OPERATOR_WORKDAY_BUSINESS_IDS','')
    assert not check_tenant_access(c,'b','admin',False,'work.colleague.send')['ok']


def test_disk_status_requires_server_encryption(workday,monkeypatch):
    _,c=workday
    monkeypatch.setenv('YANDEX_DISK_CLIENT_ID','client')
    monkeypatch.setenv('YANDEX_DISK_CLIENT_SECRET','secret')
    monkeypatch.delenv('EXTERNAL_AUTH_SECRET_KEY',raising=False)
    assert not yandex_disk.status(c,'b')['configured']


@pytest.mark.parametrize('unknown',[False,True])
def test_colleague_delivery_reuses_outbox_and_never_blindly_retries(workday,monkeypatch,unknown):
    conn,c=workday
    operator_workday.apply(c,'b','admin',prepare(c),'schedule')
    c.execute("INSERT INTO operator_pilot_settings(business_id,recipient_user_id,updated_by) VALUES ('b','u','u')")
    envelope=operator_colleagues.prepare(c,'b','admin',{'date':'2026-09-14','schedule_version':1,'message':'Предложите уход.'})['approval']['envelope']
    queued=operator_colleagues.enqueue(c,'b','admin',envelope,'approved-message')
    duplicate=operator_colleagues.enqueue(c,'b','admin',envelope,'approved-message')
    assert queued['async_job_id']==duplicate['async_job_id']
    c.execute('SELECT * FROM operator_async_jobs WHERE id=%s',(queued['async_job_id'],))
    job=dict(c.fetchone())
    conn.commit()
    class DB:
        def __init__(self):self.conn=conn
        def close(self):self.conn.rollback()
    monkeypatch.setattr(operator_colleagues,'DatabaseManager',DB)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-token')
    calls=[]
    class Response:
        status_code=200
        def json(self):return {'ok':True,'result':{'message_id':17}}
    def send(*args,**kwargs):
        calls.append(kwargs['json'])
        if unknown:raise operator_colleagues.requests.Timeout('test timeout')
        return Response()
    monkeypatch.setattr(operator_colleagues.requests,'post',send)
    result=operator_colleagues.process_job(job)
    replay=operator_colleagues.process_job(job)
    assert len(calls)==1 and calls[0]['chat_id']=='123'
    if unknown:
        assert result['delivery_state']==replay['delivery_state']=='unknown'
    else:
        assert result['provider_message_id']==replay['provider_message_id']=='17'
    c.execute('SELECT COUNT(*) n FROM journey_actions')
    assert c.fetchone()['n']==1
