"""Workday extension integration against an isolated PostgreSQL schema."""
import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from tests.test_operator_workday import workday
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import operator_attachments, operator_story, yandex_disk


def attachment(c,content,name,mime='application/octet-stream'):
    return operator_attachments.receive(c,business_id='b',user_id='admin',channel='web',content=content,name=name,mime_type=mime,request_key=name)


def test_xlsx_and_mixed_pdf_do_not_drop_rows(workday,monkeypatch):
    from openpyxl import Workbook
    import pymupdf
    _,c=workday
    workbook=Workbook();workbook.active.append(['Time','Service']);workbook.active.append(['10:00','Color'])
    buffer=io.BytesIO();workbook.save(buffer)
    item=attachment(c,buffer.getvalue(),'day.xlsx')
    assert '10:00 | Color' in operator_attachments.classify(c,'b','admin',item['id'],'schedule',item['conversation_id'])['source_text']
    document=pymupdf.open();document.new_page().insert_text((30,30),'10:00 Color');document.new_page()
    item=attachment(c,document.tobytes(),'mixed.pdf','application/pdf');document.close()
    from services import gigachat_client
    class OCR:
        def analyze_screenshot(self,*args,**kwargs):return '12:00 Care'
    monkeypatch.setattr(gigachat_client,'get_gigachat_client',lambda:OCR())
    text=operator_attachments.classify(c,'b','admin',item['id'],'schedule',item['conversation_id'])['source_text']
    assert '10:00 Color' in text and '12:00 Care' in text
    workbook.active.cell(202,1,'must not disappear');buffer=io.BytesIO();workbook.save(buffer)
    item=attachment(c,buffer.getvalue(),'large.xlsx')
    with pytest.raises(ValueError,match='200 строк'):
        operator_attachments.classify(c,'b','admin',item['id'],'schedule',item['conversation_id'])


@pytest.fixture
def media(workday,monkeypatch,tmp_path):
    conn,c=workday
    from alembic import op
    import importlib.util
    monkeypatch.setattr(op,'execute',c.execute)
    path=Path(__file__).parents[1]/'alembic_migrations/versions/20260625_add_media_intelligence.py'
    spec=importlib.util.spec_from_file_location('media_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.upgrade()
    c.execute("ALTER TABLE photo_assets ADD COLUMN IF NOT EXISTS asset_version INTEGER DEFAULT 1, ADD COLUMN IF NOT EXISTS content_hash TEXT, ADD COLUMN IF NOT EXISTS analysis_status TEXT DEFAULT 'not_analyzed'")
    monkeypatch.setenv('MEDIA_UPLOAD_DIR',str(tmp_path/'media'))
    monkeypatch.setenv('MEDIA_STORAGE_BACKEND','local')
    return conn,c


def photo(c):
    buffer=io.BytesIO();Image.new('RGB',(16,16),'red').save(buffer,format='PNG')
    item=attachment(c,buffer.getvalue(),'photo.png','image/png')
    result=operator_attachments.classify(c,'b','admin',item['id'],'content',item['conversation_id'])
    return {**item,'photo_asset_id':result['attachment']['photo_asset_id']}


def test_story_uses_existing_media_channels_history_and_invalidates_approval(media):
    _,c=media
    c.execute("""CREATE TABLE contentplans(id TEXT PRIMARY KEY,business_id TEXT,plan_status TEXT,period_start DATE,period_end DATE,
        generated_plan_json JSONB,updated_at TIMESTAMPTZ DEFAULT NOW())""")
    c.execute("""CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,business_id TEXT,theme TEXT,goal TEXT,scheduled_for DATE,
        status TEXT,content_type TEXT,source_kind TEXT,draft_text TEXT,metadata_json JSONB,updated_at TIMESTAMPTZ DEFAULT NOW())""")
    c.execute("""CREATE TABLE social_posts(id TEXT PRIMARY KEY,business_id TEXT,content_plan_item_id TEXT,status TEXT,approved_at TIMESTAMPTZ,
        approval_id TEXT,automation_task_id TEXT,updated_at TIMESTAMPTZ DEFAULT NOW(),base_text TEXT,platform_text TEXT,scheduled_for DATE,media_json JSONB DEFAULT '[]')""")
    c.execute("INSERT INTO contentplans VALUES ('p','b','generated','2026-09-01','2026-09-30','{\"selected_channels\":[\"vk\",\"telegram\"]}',NOW())")
    item=photo(c)
    args={'plan_id':'p','theme':'Результат работы','draft_text':'Уход после окрашивания.','scheduled_for':'2026-09-15','attachment_ids':[item['id']]}
    saved=operator_story.save(c,'b','admin',args,item['conversation_id'],'create')
    repeat=operator_story.save(c,'b','admin',args,item['conversation_id'],'create')
    assert repeat['item_id']==saved['item_id']
    c.execute('SELECT * FROM contentplanitems WHERE id=%s',(saved['item_id'],));old=dict(c.fetchone())
    assert old['metadata_json']['selected_channels']==['vk','telegram']
    c.execute("INSERT INTO social_posts(id,business_id,content_plan_item_id,status,approved_at,approval_id,automation_task_id,updated_at) VALUES ('post','b',%s,'approved',NOW(),'approval','task',NOW())",(saved['item_id'],))
    args.update(item_id=saved['item_id'],version=str(old['updated_at']),draft_text='Короткий рассказ.')
    args.pop('scheduled_for')
    operator_story.save(c,'b','admin',args,item['conversation_id'],'edit')
    c.execute('SELECT * FROM contentplanitems WHERE id=%s',(saved['item_id'],));new=dict(c.fetchone())
    assert new['scheduled_for']==old['scheduled_for']
    assert new['metadata_json']['operator_edit_history'][0]['draft_text']==old['draft_text']
    c.execute("SELECT status,approval_id FROM social_posts WHERE id='post'");assert dict(c.fetchone())=={'status':'needs_review','approval_id':None}
    c.execute("SELECT COUNT(*) n FROM photo_asset_usage_events WHERE usage_type='publication'");assert c.fetchone()['n']==1
    with pytest.raises(ValueError,match='изменился'):
        operator_story.save(c,'b','admin',args,item['conversation_id'],'stale')
    c.execute("UPDATE social_posts SET status='published'")
    args['version']=str(new['updated_at'])
    with pytest.raises(ValueError,match='опубликован'):
        operator_story.save(c,'b','admin',args,item['conversation_id'],'published')


@pytest.mark.parametrize('failure',[False,True])
def test_disk_sync_retry_is_idempotent_and_keeps_local_photo(media,monkeypatch,failure):
    conn,c=media
    item=photo(c)
    c.execute("INSERT INTO business_disk_connections(business_id,token_encrypted,connected_by) VALUES ('b','encrypted','u')")
    queued=yandex_disk.queue(c,'b','admin',item['photo_asset_id'])
    assert yandex_disk.queue(c,'b','admin',item['photo_asset_id'])['job_id']==queued['job_id']
    c.execute('SELECT * FROM operator_async_jobs WHERE id=%s',(queued['job_id'],));job=dict(c.fetchone())
    conn.commit()
    class DB:
        def __init__(self):self.conn=conn
        def close(self):self.conn.rollback()
    monkeypatch.setattr(yandex_disk,'DatabaseManager',DB)
    monkeypatch.setattr(yandex_disk,'decrypt_auth_data',lambda token:'test-token')
    remote={};uploads=[]
    class Response:
        def __init__(self,status,body=None):self.status_code=status;self.body=body or {}
        def json(self):return self.body
    def put(url,**kwargs):
        if failure:raise yandex_disk.requests.Timeout('test timeout')
        if url.startswith('https://upload.yandex.net/'):
            uploads.append(kwargs['data']);remote['digest']=hashlib.md5(kwargs['data']).hexdigest()
        return Response(201)
    def get(url,**kwargs):
        if url.endswith('/upload'):return Response(200,{'href':'https://upload.yandex.net/file'})
        return Response(200,{'md5':remote['digest']}) if remote else Response(404)
    monkeypatch.setattr(yandex_disk.requests,'put',put);monkeypatch.setattr(yandex_disk.requests,'get',get)
    if failure:
        with pytest.raises(ValueError,match='Фото сохранено'):yandex_disk.process_job(job)
        c.execute('SELECT status FROM photo_disk_sync');assert c.fetchone()['status']=='needs_retry'
        failure=False
    assert yandex_disk.process_job(job)['status']=='completed'
    assert yandex_disk.process_job(job)['status']=='completed'
    assert len(uploads)==1
    assert operator_attachments.file_bytes(operator_attachments.load(c,'b','admin',item['id']))
    yandex_disk.disconnect(c,'b','u');conn.commit()
    assert yandex_disk.process_job(job)['status']=='cancelled'
    assert len(uploads)==1


@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app'])
@pytest.mark.parametrize('voice',[False,True])
def test_shared_routing_schedule_review_correction_and_briefing(workday,monkeypatch,channel,voice):
    from services import operator_audio,operator_chat_service,operator_core
    from tests.test_operator_workday import entries
    conn,c=workday
    original_auth=operator_audio.authorize_actor
    def paid_actor(*args):
        actor,_=original_auth(*args)
        return actor,{'capabilities':['management','operator','finance','social_content']}
    monkeypatch.setattr(operator_audio,'authorize_actor',paid_actor)
    version=0
    def planner(state):
        if 'Проведи планёрку' in state['message']:
            return {'action':'tool_call','tool':'work.morning_briefing','arguments':{'date':'2026-09-14'}}
        return {'action':'tool_call','tool':'work.prepare_schedule','arguments':{'date':'2026-09-14','version':version,'entries':entries()}}
    def router(cursor,**args):return operator_core.route_operator_message(cursor,tool_planner=planner,**args)
    message='Сохрани расписание на 14 сентября: 10:00 и 11:30 окрашивание, мастер Первый, по 60 минут.'
    payload={'request_id':'one'}
    if voice:
        asset=operator_audio.create_transcription(c,content=b'fixture',user_id='admin',business_id='b',channel=channel,conversation_id=None,request_id='recording')
        c.execute("UPDATE operator_audio_assets SET status='ready',transcript=%s WHERE id=%s",(message,asset['asset_id']))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s",(asset['job_id'],))
        payload.update(transcription_id=asset['asset_id'],conversation_id=asset['conversation_id'])
    result=operator_chat_service.process_chat(c,business_id='b',user_id='admin',channel=channel,message=message,payload=payload,router=router)
    assert result['status']=='approval_required',json.dumps(result,ensure_ascii=False,default=str)
    saved,_=operator_core.confirm_pending_operator_action(c,action_id=result['approval']['action_id'],business_id='b',user_id='admin')
    assert saved['status']=='completed'
    version=1
    briefing=operator_chat_service.process_chat(c,business_id='b',user_id='admin',channel=channel,message='Проведи планёрку',payload={'request_id':'briefing'},router=router)
    assert briefing['schedule_version']==1 and briefing['items']
    first=operator_chat_service.process_chat(c,business_id='b',user_id='admin',channel=channel,message=message,payload={'request_id':'correction1'},router=router)
    second=operator_chat_service.process_chat(c,business_id='b',user_id='admin',channel=channel,message=message,payload={'request_id':'correction2'},router=router)
    if first['approval']['action_id']!=second['approval']['action_id']:
        denied,_=operator_core.confirm_pending_operator_action(c,action_id=first['approval']['action_id'],business_id='b',user_id='admin')
        assert denied['status']=='blocked'
    c.execute('SELECT COUNT(*) n FROM bookings');assert c.fetchone()['n']==2


def test_http_upload_settings_and_revoked_access(workday,monkeypatch):
    from flask import Flask,Blueprint
    from api import operator_workday_api
    conn,c=workday
    class DB:
        def __init__(self):self.conn=conn
        def close(self):self.conn.rollback()
    monkeypatch.setattr(operator_workday_api,'DatabaseManager',DB)
    current={'id':'admin'}
    monkeypatch.setattr(operator_workday_api,'require_auth_from_request',lambda:current)
    app=Flask(__name__);bp=Blueprint('workday_test',__name__);operator_workday_api.register_workday_routes(bp);app.register_blueprint(bp,url_prefix='/api/operator')
    client=app.test_client()
    config=client.get('/api/operator/workday/config?business_id=b')
    assert config.status_code==200 and not config.json['can_configure']
    assert client.post('/api/operator/workday/recipient',json={'business_id':'b','recipient_user_id':'u','version':0}).status_code==403
    upload=client.post('/api/operator/attachments',data={'business_id':'b','channel':'web','request_id':'http-file','file':(io.BytesIO(b'time,service\n10:00,Color'),'day.csv')})
    assert upload.status_code==200,upload.json
    conversation=upload.json['conversation_id']
    c.execute('SELECT input_context_json FROM operatorconversations WHERE id=%s',(conversation,))
    assert c.fetchone()['input_context_json']['attachment_ids']==[upload.json['attachment']['id']]
    c.execute("UPDATE business_members SET status='revoked' WHERE user_id='admin'");conn.commit()
    assert client.get('/api/operator/disk/status?business_id=b').status_code==403
    current={'id':'u'}
    assert client.post('/api/operator/workday/recipient',json={'business_id':'b','recipient_user_id':'u','version':0}).status_code==200
    assert client.post('/api/operator/workday/recipient',json={'business_id':'b','recipient_user_id':'u','version':0}).status_code==400


def test_oauth_state_is_single_use_and_owner_bound(workday,monkeypatch):
    _,c=workday
    monkeypatch.setattr(yandex_disk,'configuration',lambda:('client','secret','https://localos.pro/api/operator/disk/callback'))
    from urllib.parse import urlparse,parse_qs
    with pytest.raises(PermissionError):yandex_disk.begin(c,'b','admin')
    link=yandex_disk.begin(c,'b','u')['url'];state=parse_qs(urlparse(link).query)['state'][0]
    class Response:
        status_code=200
        def json(self):return {'access_token':'plain-token'}
    monkeypatch.setattr(yandex_disk.requests,'post',lambda *args,**kwargs:Response())
    monkeypatch.setattr(yandex_disk.requests,'get',lambda *args,**kwargs:Response())
    monkeypatch.setattr(yandex_disk,'encrypt_auth_data',lambda value:'encrypted-token')
    with pytest.raises(ValueError):yandex_disk.finish(c,'wrong', 'code')
    assert yandex_disk.finish(c,state,'code')==('b','u')
    c.execute('SELECT token_encrypted FROM business_disk_connections')
    assert c.fetchone()['token_encrypted']=='encrypted-token'
    with pytest.raises(ValueError):yandex_disk.finish(c,state,'code')


def test_telegram_album_keeps_caption_and_same_conversation(workday,monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from services import operator_telegram_inputs
    conn,c=workday
    buffer=io.BytesIO();Image.new('RGB',(16,16),'blue').save(buffer,format='PNG');content=buffer.getvalue()
    monkeypatch.setattr(operator_telegram_inputs,'transaction',lambda operation:operation(conn.cursor()))
    host=SimpleNamespace(user_states={},_control_scope_business_context=lambda user:{'business_id':'b','user_id':'admin'})
    replies=[]
    async def reply(text):replies.append(text)
    class Bot:
        async def get_file(self,identifier):return self
        async def download_as_bytearray(self):return bytearray(content)
    async def run():
        for index in [1,2]:
            message=SimpleNamespace(document=SimpleNamespace(file_size=len(content),file_id=str(index),file_name='album.png',mime_type='application/octet-stream'),photo=[],caption='Результат окрашивания' if index==1 else None,message_id=index,reply_text=reply)
            update=SimpleNamespace(effective_chat=SimpleNamespace(type='private',id=123),effective_user=SimpleNamespace(is_bot=False,id=123),message=message)
            assert await operator_telegram_inputs.receive(update,SimpleNamespace(bot=Bot()),host)
    asyncio.run(run())
    c.execute('SELECT input_context_json FROM operatorconversations');context=c.fetchone()['input_context_json']
    assert len(context['attachment_ids'])==2 and len(context['attachment_notes'])==1
    assert len(replies)==2
    c.execute('SELECT COUNT(DISTINCT conversation_id) n FROM operator_attachments');assert c.fetchone()['n']==1
