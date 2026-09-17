import hashlib
from urllib.parse import urlparse, parse_qs
import pytest
from tests.test_operator_workday import workday
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from tests.test_operator_workday_integration import media, photo
from services import google_drive


class Response:
    def __init__(self,status,body=None):self.status_code=status;self.body=body or {}
    def json(self):return self.body


def test_oauth_owner_scope_single_use_and_encryption(workday,monkeypatch):
    _,c=workday
    monkeypatch.setenv('EXTERNAL_AUTH_SECRET_KEY','unit-test-only-key')
    monkeypatch.setattr(google_drive,'configuration',lambda *args:('client','secret','https://localos.pro/api/operator/google-drive/callback'))
    with pytest.raises(PermissionError):google_drive.begin(c,'b','admin')
    query=parse_qs(urlparse(google_drive.begin(c,'b','u')['url']).query)
    assert query['scope']==[google_drive.SCOPE] and query['access_type']==['offline']
    monkeypatch.setattr(google_drive.requests,'post',lambda *a,**k:Response(200,{'access_token':'access','refresh_token':'refresh','scope':google_drive.SCOPE}))
    assert google_drive.finish(c,query['state'][0],'code')==('b','u')
    with pytest.raises(ValueError):google_drive.finish(c,query['state'][0],'code')
    c.execute('SELECT token_encrypted FROM business_google_drive_connections');assert 'refresh' not in c.fetchone()['token_encrypted']
    assert google_drive.access_token({'token_encrypted':google_drive.encrypt_auth_data('{"refresh_token":"refresh"}')})=='access'
    query=parse_qs(urlparse(google_drive.begin(c,'b','u')['url']).query)
    monkeypatch.setattr(google_drive.requests,'post',lambda *a,**k:Response(200,{'access_token':'access','refresh_token':'refresh','scope':'wrong'}))
    with pytest.raises(ValueError):google_drive.finish(c,query['state'][0],'code')


def test_sync_timeout_reuses_committed_google_id_and_disconnect_keeps_local(media,monkeypatch):
    conn,c=media
    item=photo(c)
    c.execute("INSERT INTO business_google_drive_connections(business_id,token_encrypted,connected_by) VALUES ('b','secret','u')")
    queued=google_drive.queue(c,'b','admin',item['photo_asset_id'])
    assert google_drive.queue(c,'b','admin',item['photo_asset_id'])['job_id']==queued['job_id']
    c.execute('SELECT * FROM operator_async_jobs WHERE id=%s',(queued['job_id'],));job=dict(c.fetchone());conn.commit()
    class DB:
        def __init__(self):self.conn=conn
        def close(self):pass
    monkeypatch.setattr(google_drive,'DatabaseManager',DB)
    monkeypatch.setattr(google_drive,'access_token',lambda _: 'access')
    objects={};uploads=[];ids=[]
    from services.media_file_storage import load_media_file
    c.execute('SELECT versions_json FROM photo_assets WHERE id=%s',(item['photo_asset_id'],))
    storage_path=c.fetchone()['versions_json']['original']['storage_path']
    content=load_media_file(storage_path)
    def get(url,**kwargs):
        if url.endswith('generateIds'):
            identifier='remote'+str(len(ids));ids.append(identifier);return Response(200,{'ids':[identifier]})
        identifier=url.rsplit('/',1)[-1]
        return Response(200,objects[identifier]) if identifier in objects else Response(404)
    def post(url,**kwargs):
        if 'upload/drive' in url:
            import json
            payload=kwargs['data'].split(b'\r\n\r\n')[1].split(b'\r\n--')[0]
            identifier=json.loads(payload)['id'];uploads.append(identifier)
            objects[identifier]={'id':identifier,'md5Checksum':hashlib.md5(content).hexdigest()}
            raise google_drive.requests.Timeout('uncertain upload')
        identifier=kwargs['json']['id'];objects[identifier]={'id':identifier};return Response(200,objects[identifier])
    monkeypatch.setattr(google_drive.requests,'get',get);monkeypatch.setattr(google_drive.requests,'post',post)
    with pytest.raises(ValueError):google_drive.process_job(job)
    assert google_drive.process_job(job)['status']=='completed'
    assert len(uploads)==1 and len(ids)==4
    google_drive.disconnect(c,'b','u');conn.commit()
    assert google_drive.process_job(job)['status']=='cancelled'
    assert load_media_file(storage_path)


def test_missing_credentials_and_revoked_token(workday,monkeypatch):
    _,c=workday
    monkeypatch.delenv('GOOGLE_DRIVE_CLIENT_ID',raising=False)
    assert not google_drive.status(c,'b')['configured']
    monkeypatch.setattr(google_drive,'configuration',lambda *args:('c','s','redirect'))
    monkeypatch.setattr(google_drive,'decrypt_auth_data',lambda _:'{"refresh_token":"secret"}')
    monkeypatch.setattr(google_drive.requests,'post',lambda *a,**k:Response(400,{'error':'invalid_grant'}))
    with pytest.raises(ValueError,match='Подключите'):google_drive.access_token({'token_encrypted':'encrypted'})


def test_http_google_settings_owner_only_and_business_isolation(workday,monkeypatch):
    from flask import Flask,Blueprint
    from api import operator_workday_api
    conn,c=workday
    class DB:
        def __init__(self):self.conn=conn
        def close(self):self.conn.rollback()
    monkeypatch.setattr(operator_workday_api,'DatabaseManager',DB)
    current={'id':'admin'}
    monkeypatch.setattr(operator_workday_api,'require_auth_from_request',lambda:current)
    app=Flask(__name__);bp=Blueprint('google_test',__name__)
    operator_workday_api.register_workday_routes(bp);app.register_blueprint(bp,url_prefix='/api/operator')
    client=app.test_client()
    assert client.get('/api/operator/google-drive/status?business_id=b').status_code==200
    for action in ('connect','disconnect','retry'):
        assert client.post('/api/operator/google-drive/'+action,json={'business_id':'b'}).status_code==403
    assert client.get('/api/operator/google-drive/status?business_id=other').status_code==403
    current={'id':'u'}
    assert client.post('/api/operator/google-drive/disconnect',json={'business_id':'b'}).status_code==200
    assert client.get('/api/operator/google-drive/callback?state=wrong&code=bad').status_code==400


def test_deleted_or_modified_remote_file_is_never_overwritten(monkeypatch):
    monkeypatch.setattr(google_drive.requests,'get',lambda *a,**k:Response(200,{'trashed':True}))
    def unexpected(*args,**kwargs):pytest.fail('Must not upload over removed file')
    monkeypatch.setattr(google_drive.requests,'post',unexpected)
    with pytest.raises(ValueError):google_drive.ensure_file('id','photo','folder',{},b'photo','image/jpeg')
