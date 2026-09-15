import io
import json
import importlib.util
from pathlib import Path
import pytest
from PIL import Image
from tests.test_operator_workday_integration import media
from tests.test_operator_workday import workday
from tests.test_work_journal_pg import journal
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import disk_import, disk_import_providers, disk_import_media

@pytest.fixture
def inbox(media,monkeypatch):
    conn,c=media
    c.execute('CREATE TABLE contentplans(id TEXT PRIMARY KEY,business_id TEXT)')
    c.execute("CREATE TABLE contentplanitems(id TEXT PRIMARY KEY,plan_id TEXT,status TEXT,updated_at TIMESTAMPTZ DEFAULT clock_timestamp())")
    c.execute("CREATE TABLE social_posts(id TEXT PRIMARY KEY,business_id TEXT,content_plan_item_id TEXT,status TEXT,approved_at TIMESTAMPTZ,approval_id TEXT,automation_task_id TEXT,metadata_json JSONB,updated_at TIMESTAMPTZ,last_error TEXT)")
    from alembic import op
    monkeypatch.setattr(op,'execute',c.execute)
    spec=importlib.util.spec_from_file_location('inbox_migration',Path(__file__).parents[1]/'alembic_migrations/versions/20260915_disk_import.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.upgrade();module.upgrade()
    monkeypatch.setenv('DISK_IMPORT_BUSINESS_IDS','b,b2')
    from services import operator_audio
    def auth(cursor,user,business,**kwargs):
        cursor.execute('SELECT is_active FROM users WHERE id=%s',(user,));row=cursor.fetchone()
        if not row or not row['is_active']:raise PermissionError('Inactive')
        cursor.execute('SELECT owner_id FROM businesses WHERE id=%s',(business,));row=cursor.fetchone()
        if row and row['owner_id']==user:return {'role':'business_owner'},{}
        cursor.execute("SELECT role FROM business_members WHERE business_id=%s AND user_id=%s AND status='active'",(business,user))
        if not cursor.fetchone():raise PermissionError('No membership')
        return {'role':'business_user'},{}
    monkeypatch.setattr(operator_audio,'authorize_actor',auth)
    c.execute("INSERT INTO disk_import_sources(id,business_id,provider,root_id,connected_by,credential_identity,state) VALUES ('s','b','google','root','u','reader','active')")
    class Reader:
        pages={('root',None):([],None)}
        downloads=[]
        def page(self,folder,token=None):
            value=self.pages[(folder,token)]
            if isinstance(value,Exception):raise value
            return value
        def download(self,file):
            self.downloads.append(file['id']);buffer=io.BytesIO();Image.new('RGB',(16,16),'blue' if file['revision']=='v2' else 'red').save(buffer,format='PNG');return buffer.getvalue()
        def validate_file(self,file):pass
    reader=Reader();monkeypatch.setattr(disk_import_providers,'reader',lambda *_:reader)
    return conn,c,reader

def file(identifier='photo',revision='v1',kind='photo'):
    return {'id':identifier,'revision':revision,'name':identifier+'.png' if kind=='photo' else identifier+'.mp4','kind':kind,'mime_type':'image/png' if kind=='photo' else 'video/mp4','size':100,'url':'https://drive.google.com/file/d/'+identifier+'/view'}

def scan(c,reader,entries):
    reader.pages[('root',None)]=(entries,None)
    source=disk_import.load(c,'b','s');disk_import.enqueue_scan(c,source)
    source=disk_import.load(c,'b','s');disk_import.process_scan(c,source,{'scan_id':source['scan_id'],'sequence':source['scan_sequence']})
    for entry in entries:
        if entry['kind'] in {'photo','video'}:disk_import.process_file(c,source,{'external_id':entry['id'],'revision':entry['revision']})

def test_import_dedup_revision_video_and_deletion(inbox):
    _,c,r=inbox
    scan(c,r,[file(),file('duplicate'),file('video',kind='video')])
    c.execute('SELECT COUNT(*) n FROM photo_assets');assert c.fetchone()['n']==1
    assert r.downloads==['photo','duplicate']
    c.execute('SELECT id FROM photo_assets');old=c.fetchone()['id']
    scan(c,r,[{**file(),'name':'renamed.png'},file('video',kind='video')]);assert r.downloads==['photo','duplicate']
    scan(c,r,[file(revision='v2'),file('video',kind='video')])
    c.execute('SELECT COUNT(*) n FROM photo_assets');assert c.fetchone()['n']==2
    c.execute('SELECT metadata_json FROM photo_assets WHERE id=%s',(old,));assert c.fetchone()['metadata_json']['disk_import_available'] is False
    scan(c,r,[])
    c.execute('SELECT COUNT(*) n FROM external_video_assets WHERE available');assert c.fetchone()['n']==0
    c.execute('SELECT COUNT(*) n FROM photo_assets');assert c.fetchone()['n']==2
    c.execute('SELECT COUNT(*) n FROM disk_import_revisions');assert c.fetchone()['n']==4

def test_pagination_error_does_not_remove_and_resumes(inbox):
    _,c,r=inbox;scan(c,r,[file()])
    source=disk_import.load(c,'b','s');disk_import.enqueue_scan(c,source)
    r.pages[('root',None)]=([], 'next')
    source=disk_import.load(c,'b','s');disk_import.process_scan(c,source,{'scan_id':source['scan_id'],'sequence':0})
    source=disk_import.load(c,'b','s');assert source['pending_json'][0]['token']=='next'
    r.pages[('root','next')]=disk_import_providers.AccessLost('revoked')
    with pytest.raises(disk_import_providers.AccessLost):disk_import.process_scan(c,source,{'scan_id':source['scan_id'],'sequence':1})
    c.execute('SELECT available FROM disk_import_files');assert c.fetchone()['available']
    r.pages[('root','next')]=([file()],None)
    disk_import.process_scan(c,source,{'scan_id':source['scan_id'],'sequence':1})
    c.execute('SELECT available FROM disk_import_files');assert c.fetchone()['available']

def test_permissions_versions_and_voice_queue(inbox):
    _,c,r=inbox
    with pytest.raises(PermissionError):disk_import.action(c,'b','admin',{'source_id':'s','version':1,'action':'pause'})
    with pytest.raises(PermissionError):disk_import.load(c,'b2','s')
    with pytest.raises(ValueError):disk_import.action(c,'b','u',{'source_id':'s','version':0,'action':'pause'})
    source=disk_import.load(c,'b','s');disk_import.enqueue_scan(c,source)
    from services.operator_async_jobs import claim_next_operator_async_job
    assert claim_next_operator_async_job(c) is None
    assert claim_next_operator_async_job(c,background=True)['kind']=='disk_import_scan'
    result=disk_import.action(c,'b','u',{'source_id':'s','version':1,'action':'pause'});assert result['version']==2

def test_selection_history_invalidation_and_manual_boundary(inbox):
    _,c,r=inbox;scan(c,r,[file('video',kind='video')])
    c.execute("INSERT INTO contentplans VALUES ('plan','b')");c.execute("INSERT INTO contentplanitems(id,plan_id,status) VALUES ('item','plan','draft')")
    c.execute("INSERT INTO social_posts(id,business_id,content_plan_item_id,status,approved_at,approval_id) VALUES ('post','b','item','approved',NOW(),'approved')")
    listing=disk_import_media.listing(c,'b','u','item');identifier=listing['videos'][0]['id']
    result=disk_import_media.attach(c,'b','u',{'item_id':'item','item_version':listing['item_version'],'video_ids':[identifier]});assert result['selected'][0]['id']==identifier
    c.execute("SELECT status,approval_id FROM social_posts WHERE id='post'");assert dict(c.fetchone())=={'status':'needs_review','approval_id':None}
    from services.social_posts import recommendations_handoff,launch_proof
    post={'id':'post','business_id':'b','content_plan_item_id':'item','platform':'telegram'}
    assert recommendations_handoff._publish_api_post(c,post)['status']=='needs_manual_publish'
    with pytest.raises(ValueError,match='вручную'):launch_proof._create_supervised_publish_task(c,post)
    scan(c,r,[]);assert disk_import_media.selected(c,'b','item')[0]['available'] is False
    assert disk_import_media.listing(c,'b','u','item')['videos']==[]
    with pytest.raises(ValueError):disk_import_media.attach(c,'b','u',{'item_id':'item','item_version':result['item_version'],'video_ids':[identifier]})

@pytest.mark.parametrize('url',['http://drive.google.com/drive/folders/a','https://evil.test/drive/folders/a','https://drive.google.com/file/d/a','https://drive.google.com/drive/folders/a\'b'])
def test_folder_input_is_narrow(url):
    with pytest.raises(ValueError):disk_import_providers.google_folder_id(url)

def test_google_does_not_reconcile_incomplete_or_inaccessible_root(monkeypatch):
    reader=object.__new__(disk_import_providers.GoogleReader);reader.source={'root_id':'root'};reader.headers={}
    monkeypatch.setattr(reader,'metadata',lambda _: {'mimeType':disk_import_providers.FOLDER})
    class Response:
        status_code=200
        def json(self):return {'files':[],'incompleteSearch':True}
    monkeypatch.setattr(disk_import_providers.requests,'get',lambda *a,**k:Response())
    with pytest.raises(ValueError,match='неполный'):reader.page('root')
    monkeypatch.setattr(reader,'metadata',lambda _: {'mimeType':disk_import_providers.FOLDER,'trashed':True})
    with pytest.raises(disk_import_providers.AccessLost):reader.page('root')

def test_heic_conversion_and_bound():
    import pillow_heif
    pillow_heif.register_heif_opener();buffer=io.BytesIO();Image.new('RGB',(16,16),'red').save(buffer,format='HEIF')
    content,name,mime=disk_import.normalize_photo(buffer.getvalue(),'work.heic','image/heic')
    assert name=='work.jpg' and mime=='image/jpeg' and Image.open(io.BytesIO(content)).format=='JPEG'
    with pytest.raises(ValueError,match='photo_too_large'):disk_import.normalize_photo(b'x'*(disk_import_providers.MAX_BYTES+1),'x.png','image/png')

def test_google_proof_single_use_empty_expiry_and_cross_business(inbox,monkeypatch):
    _,c,r=inbox
    c.execute("UPDATE disk_import_sources SET state='disconnected'")
    c.execute("INSERT INTO disk_import_credentials(id,client_email,secret_encrypted,updated_by) VALUES ('google_reader','reader','encrypted','u')")
    prepared=disk_import.prepare(c,'b','u',{'provider':'google','folder_url':'https://drive.google.com/drive/folders/root'})
    identifier=prepared['id'];code=prepared['proof_folder_name'];r.headers={}
    r.metadata=lambda _: {'name':'Client folder','mimeType':disk_import_providers.FOLDER}
    class Response:
        status_code=200
        def json(self):return {'files':[{'id':'proof'}]}
    monkeypatch.setattr(disk_import_providers.requests,'get',lambda *a,**k:Response())
    r.pages[('proof',None)]=([file()],None)
    with pytest.raises(ValueError,match='пустой'):disk_import.verify(c,'b','u',{'source_id':identifier,'code':code})
    r.pages[('proof',None)]=([],None)
    with pytest.raises(ValueError,match='истёк'):disk_import.verify(c,'b','u',{'source_id':identifier,'code':'wrong'})
    assert disk_import.verify(c,'b','u',{'source_id':identifier,'code':code})['state']=='ready'
    with pytest.raises(ValueError,match='использован'):disk_import.verify(c,'b','u',{'source_id':identifier,'code':code})
    c.execute("INSERT INTO businesses(id,owner_id) VALUES ('b2','u')")
    other=disk_import.prepare(c,'b2','u',{'provider':'google','folder_url':'https://drive.google.com/drive/folders/root'})
    with pytest.raises(ValueError,match='уже подключена'):disk_import.verify(c,'b2','u',{'source_id':other['id'],'code':other['proof_folder_name']})
    c.execute("UPDATE disk_import_sources SET challenge_expires_at=NOW()-INTERVAL '1 second' WHERE id=%s",(other['id'],))
    with pytest.raises(ValueError,match='истёк'):disk_import.verify(c,'b2','u',{'source_id':other['id'],'code':other['proof_folder_name']})

def test_skips_invalid_files_and_shortcuts(inbox):
    _,c,r=inbox
    scan(c,r,[{**file(),'size':disk_import_providers.MAX_BYTES+1}, {**file('shortcut',kind='unsupported'),'mime_type':'application/vnd.google-apps.shortcut'}])
    c.execute('SELECT error_code FROM disk_import_files ORDER BY external_id')
    assert [row['error_code'] for row in c.fetchall()]==['photo_too_large','unsupported_format']
    assert r.downloads==[]

def test_worker_revoke_stale_and_disconnect_retains_history(inbox,monkeypatch):
    conn,c,r=inbox;scan(c,r,[file(),file('video',kind='video')]);conn.commit()
    class DB:
        def __init__(self):self.conn=conn
        def close(self):self.conn.rollback()
    monkeypatch.setattr(disk_import,'DatabaseManager',DB)
    job={'business_id':'b','kind':'disk_import_file','payload_json':{'source_id':'s','version':0,'external_id':'photo','revision':'v1'}}
    assert disk_import.process_job(job)['status']=='cancelled'
    c.execute("UPDATE businesses SET owner_id='admin' WHERE id='b'");conn.commit()
    job['payload_json']['version']=1
    with pytest.raises(ValueError):disk_import.process_job(job)
    c.execute("SELECT state FROM disk_import_sources WHERE id='s'");assert c.fetchone()['state']=='needs_reconnect'
    c.execute("SELECT COUNT(*) n FROM photo_assets");assert c.fetchone()['n']==1
    c.execute("UPDATE businesses SET owner_id='u' WHERE id='b'")
    disk_import.action(c,'b','u',{'source_id':'s','version':1,'action':'disconnect'})
    c.execute('SELECT available FROM external_video_assets');assert c.fetchone()['available'] is False

def test_credentials_encrypted_write_only_and_fixed_endpoint(inbox,monkeypatch):
    _,c,r=inbox
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    monkeypatch.setenv('EXTERNAL_AUTH_SECRET_KEY',Fernet.generate_key().decode())
    from services import storage_oauth_settings
    monkeypatch.setattr(storage_oauth_settings,'authorize',lambda *args:None)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
    info={'type':'service_account','client_email':'reader@test.iam.gserviceaccount.com','private_key':key,'token_uri':'https://evil.test/token'}
    result=disk_import_providers.save_google_settings(c,'u',{'version':0,'credentials':info})
    assert set(result)=={'configured','client_email','version'}
    c.execute('SELECT secret_encrypted FROM disk_import_credentials');encrypted=c.fetchone()['secret_encrypted'];assert key not in encrypted
    decrypted=json.loads(disk_import_providers.decrypt_auth_data(encrypted));assert decrypted['token_uri']=='https://oauth2.googleapis.com/token'
    with pytest.raises(ValueError,match='изменились'):disk_import_providers.save_google_settings(c,'u',{'version':0,'credentials':info})

def test_yandex_pages_stay_inside_app_folder(monkeypatch):
    reader=object.__new__(disk_import_providers.YandexReader);reader.source={'root_id':'app:/LocalOS/b/Входящие'};reader.headers={}
    calls=[]
    class Response:
        status_code=200
        def json(self):return {'_embedded':{'items':[{'name':'work.mp4','resource_id':'stable','type':'file','mime_type':'video/mp4','md5':'hash','path':'disk:/Приложения/LocalOS/b/Входящие/work.mp4'}],'offset':0,'total':2}}
    def get(url,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setattr(disk_import_providers.requests,'get',get)
    entries,token=reader.page(reader.source['root_id']);assert token==1
    assert entries[0]['id']=='stable' and entries[0]['kind']=='video'
    assert entries[0]['path'].startswith('app:/LocalOS/b/Входящие/')
    assert calls[0]['params']['limit']==100
    with pytest.raises(disk_import_providers.AccessLost):reader.page('disk:/all-private-photos')
    assert len(calls)==1

def test_nested_scan_is_resumable_and_business_queue_is_fair(inbox):
    _,c,r=inbox
    r.pages[('root',None)]=([{'id':'sub','kind':'folder'}],None);r.pages[('sub',None)]=([file()],None)
    source=disk_import.load(c,'b','s');disk_import.enqueue_scan(c,source)
    source=disk_import.load(c,'b','s');disk_import.process_scan(c,source,{'scan_id':source['scan_id'],'sequence':0})
    resumed=disk_import.load(c,'b','s');assert resumed['pending_json']==[{'id':'sub','token':None}]
    disk_import.process_scan(c,resumed,{'scan_id':resumed['scan_id'],'sequence':1})
    c.execute("SELECT external_id FROM disk_import_files");assert c.fetchone()['external_id']=='photo'
    from services.operator_async_jobs import create_operator_async_job,claim_next_operator_async_job
    c.execute("INSERT INTO businesses(id,owner_id) VALUES ('b2','u')")
    create_operator_async_job(c,user_id='u',business_id='b2',action_id=None,kind='disk_import_scan',payload={},idempotency_key='other-business',stage='scan')
    c.execute("UPDATE operator_async_jobs SET status='completed',updated_at=clock_timestamp() WHERE business_id='b' AND kind='disk_import_scan'")
    assert claim_next_operator_async_job(c,background=True)['business_id']=='b2'

def test_stream_limit_closes_response():
    class Response:
        status_code=200;closed=False
        def iter_content(self,_):yield b'x'*(disk_import_providers.MAX_BYTES+1)
        def close(self):self.closed=True
    response=Response()
    with pytest.raises(ValueError,match='photo_too_large'):disk_import_providers.bounded_download(response)
    assert response.closed

def test_handed_off_post_cannot_gain_video_mid_publication(inbox):
    _,c,r=inbox;scan(c,r,[file('video',kind='video')])
    c.execute("INSERT INTO contentplans VALUES ('plan','b')");c.execute("INSERT INTO contentplanitems(id,plan_id,status) VALUES ('item','plan','draft')")
    c.execute("INSERT INTO social_posts(id,business_id,content_plan_item_id,status,automation_task_id) VALUES ('post','b','item','needs_supervised_publish','task')")
    current=disk_import_media.listing(c,'b','u','item')
    with pytest.raises(ValueError,match='передан на размещение'):disk_import_media.attach(c,'b','u',{'item_id':'item','item_version':current['item_version'],'video_ids':[current['videos'][0]['id']]})
