"""Private app-folder sync; media assets remain the content-plan source of truth."""
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from auth_encryption import encrypt_auth_data, decrypt_auth_data
from database_manager import DatabaseManager
from services.operator_conversations import _row
from services import operator_workday

API='https://www.googleapis.com/drive/v3'
SCOPE='https://www.googleapis.com/auth/drive.file'
TOKEN_URL='https://oauth2.googleapis.com/token'


def configuration():
    import auth_encryption
    if not auth_encryption.CRYPTOGRAPHY_AVAILABLE or not os.getenv('EXTERNAL_AUTH_SECRET_KEY','').strip():
        raise ValueError('Шифрование подключения Диска не настроено оператором LocalOS.')
    client=os.getenv('GOOGLE_DRIVE_CLIENT_ID','')
    secret=os.getenv('GOOGLE_DRIVE_CLIENT_SECRET','')
    redirect=os.getenv('GOOGLE_DRIVE_REDIRECT_URI','https://localos.pro/api/operator/google-drive/callback')
    if not client or not secret:raise ValueError('Подключение Google Диска ещё не настроено оператором LocalOS.')
    return client,secret,redirect


def status(cursor,business):
    cursor.execute('SELECT status,version,updated_at FROM business_google_drive_connections WHERE business_id=%s',(business,))
    connection=_row(cursor,cursor.fetchone())
    cursor.execute('SELECT status,COUNT(*) count FROM photo_google_drive_sync WHERE business_id=%s AND connection_version=(SELECT version FROM business_google_drive_connections WHERE business_id=%s) GROUP BY status',(business,business))
    photos=[_row(cursor,r) for r in cursor.fetchall()]
    configured=True
    try:
        configuration()
    except ValueError:
        configured=False
    return {'connection':connection or {'status':'disconnected'},'photos':photos,'configured':configured}


def begin(cursor,business,user):
    operator_workday.authorize(cursor,business,user,owner=True)
    client,_,redirect=configuration()
    state=secrets.token_urlsafe(32)
    cursor.execute("INSERT INTO business_google_drive_oauth_states(state_hash,business_id,user_id,expires_at) VALUES (%s,%s,%s,NOW()+INTERVAL '10 minutes')",
        (hashlib.sha256(state.encode()).hexdigest(),business,user))
    return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'response_type':'code','client_id':client,'redirect_uri':redirect,
            'scope':SCOPE,'state':state,'access_type':'offline','prompt':'consent'})}


def finish(cursor,state,code):
    client,secret,redirect=configuration()
    cursor.execute('SELECT * FROM business_google_drive_oauth_states WHERE state_hash=%s AND used_at IS NULL AND expires_at>NOW() FOR UPDATE',
                   (hashlib.sha256(state.encode()).hexdigest(),))
    row=_row(cursor,cursor.fetchone())
    if not row:raise ValueError('Ссылка подключения истекла или уже использована. Начните подключение заново.')
    operator_workday.authorize(cursor,row['business_id'],row['user_id'],owner=True)
    response=requests.post(TOKEN_URL,data={'grant_type':'authorization_code','code':code,
        'client_id':client,'client_secret':secret,'redirect_uri':redirect},timeout=(10,30))
    body=response.json()
    if response.status_code!=200 or not body.get('access_token'):
        raise ValueError('Google не подтвердил подключение. Начните подключение заново.')
    if SCOPE not in body.get('scope','').split() or not body.get('refresh_token'):
        raise ValueError('Google не предоставил постоянный доступ к файлам приложения. Подключите заново.')
    token=json.dumps({'refresh_token':body['refresh_token']})
    lock(cursor,row['business_id'])
    cursor.execute('''INSERT INTO business_google_drive_connections(business_id,token_encrypted,connected_by)
        VALUES (%s,%s,%s) ON CONFLICT(business_id) DO UPDATE SET token_encrypted=EXCLUDED.token_encrypted,
        connected_by=EXCLUDED.connected_by,status='connected',version=business_google_drive_connections.version+1,updated_at=NOW()''',
        (row['business_id'],encrypt_auth_data(token),row['user_id']))
    cursor.execute('UPDATE business_google_drive_oauth_states SET used_at=NOW() WHERE state_hash=%s',(row['state_hash'],))
    return row['business_id'],row['user_id']


def disconnect(cursor,business,user):
    operator_workday.authorize(cursor,business,user,owner=True)
    lock(cursor,business)
    cursor.execute("UPDATE business_google_drive_connections SET token_encrypted=NULL,status='disconnected',version=version+1,updated_at=NOW() WHERE business_id=%s",(business,))
    return {'success':True}


def queue(cursor,business,user,photo_id):
    operator_workday.authorize(cursor,business,user)
    cursor.execute("SELECT version FROM business_google_drive_connections WHERE business_id=%s AND status='connected'",(business,))
    connection=_row(cursor,cursor.fetchone())
    if not connection:return {'status':'local_only'}
    cursor.execute('SELECT asset_version FROM photo_assets WHERE id=%s AND business_id=%s',(photo_id,business))
    photo=_row(cursor,cursor.fetchone())
    if not photo:raise PermissionError('Фото недоступно.')
    version=photo.get('asset_version') or 1
    cursor.execute('''INSERT INTO photo_google_drive_sync(photo_asset_id,business_id,asset_version,connection_version)
        VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(photo_id,business,version,connection['version']))
    from services.operator_async_jobs import create_operator_async_job
    key=f"google-drive:{business}:{photo_id}:{version}:{connection['version']}"
    job=create_operator_async_job(cursor,user_id=user,business_id=business,action_id=None,kind='google_drive_sync',
        payload={'photo_id':photo_id,'asset_version':version,'connection_version':connection['version']},idempotency_key=key,stage='Сохраняю фото на Диске',max_attempts=3)
    return {'status':'queued','job_id':job['id']}


def queue_operator_photos(cursor,business,user):
    cursor.execute("SELECT DISTINCT photo_asset_id FROM operator_attachments WHERE business_id=%s AND purpose='content' AND photo_asset_id IS NOT NULL LIMIT 1000",(business,))
    ids=[_row(cursor,row)['photo_asset_id'] for row in cursor.fetchall()]
    for identifier in ids:queue(cursor,business,user,identifier)
    return len(ids)



def lock(cursor,business):
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('google-drive:'+business,))


class ReconnectRequired(ValueError):
    pass


def access_token(connection):
    client,secret,_=configuration()
    stored=json.loads(decrypt_auth_data(connection['token_encrypted']))
    response=requests.post(TOKEN_URL,data={'grant_type':'refresh_token','refresh_token':stored['refresh_token'],
        'client_id':client,'client_secret':secret},timeout=(10,30))
    if response.status_code==400 and response.json().get('error')=='invalid_grant':
        raise ReconnectRequired('Google отозвал доступ. Подключите Диск заново.')
    if response.status_code!=200 or not response.json().get('access_token'):
        raise ValueError('Google временно не подтвердил доступ. Повторите синхронизацию.')
    return response.json()['access_token']


def remote_id(cursor,conn,business,version,path,headers):
    cursor.execute('SELECT remote_id FROM google_drive_objects WHERE business_id=%s AND connection_version=%s AND path=%s',
                   (business,version,path))
    saved=_row(cursor,cursor.fetchone())
    if saved:return saved['remote_id']
    response=requests.get(API+'/files/generateIds',params={'count':1,'space':'drive','type':'files'},headers=headers,timeout=(10,30))
    if response.status_code!=200:raise ValueError('Не удалось подготовить файл Google Диска.')
    identifier=response.json()['ids'][0]
    cursor.execute('INSERT INTO google_drive_objects(business_id,connection_version,path,remote_id) VALUES (%s,%s,%s,%s)',
                   (business,version,path,identifier))
    # Commit BEFORE external creation. Session lock prevents concurrent disconnect/reconnect.
    conn.commit()
    return identifier


def ensure_file(identifier,name,parent,headers,content=None,mime=None):
    existing=requests.get(API+'/files/'+identifier,params={'fields':'id,md5Checksum,trashed'},headers=headers,timeout=(10,30))
    if existing.status_code==200:
        body=existing.json()
        if body.get('trashed') or (content is not None and body.get('md5Checksum')!=hashlib.md5(content).hexdigest()):
            raise ValueError('Файл на Google Диске изменён или удалён. Автоматическая перезапись отключена.')
        return
    if existing.status_code!=404:raise ValueError('Google Диск недоступен.')
    metadata={'id':identifier,'name':name,'mimeType':mime or 'application/vnd.google-apps.folder'}
    if parent:metadata['parents']=[parent]
    if content is None:
        response=requests.post(API+'/files',json=metadata,headers=headers,timeout=(10,30))
    else:
        boundary='localos_'+secrets.token_hex(24)
        payload=(('--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+json.dumps(metadata)+
                  '\r\n--'+boundary+'\r\nContent-Type: '+mime+'\r\n\r\n').encode()+content+
                 ('\r\n--'+boundary+'--\r\n').encode())
        response=requests.post('https://www.googleapis.com/upload/drive/v3/files',params={'uploadType':'multipart'},
            headers={**headers,'Content-Type':'multipart/related; boundary='+boundary},data=payload,timeout=(10,60))
    if response.status_code not in {200,201,409}:raise ValueError('Google Диск не подтвердил сохранение.')
    verify=requests.get(API+'/files/'+identifier,params={'fields':'id,md5Checksum,trashed'},headers=headers,timeout=(10,30))
    if verify.status_code!=200 or verify.json().get('trashed') or (content is not None and verify.json().get('md5Checksum')!=hashlib.md5(content).hexdigest()):
        raise ValueError('Сохранение ещё не подтверждено. Повторите синхронизацию.')


def process_job(job):
    db=DatabaseManager();c=db.conn.cursor();business=job['business_id'];data=job['payload_json']
    key=(data['photo_id'],data['asset_version'],data['connection_version'])
    locked=False
    try:
        c.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))',('google-drive:'+business,));locked=True
        operator_workday.authorize(c,business,job['user_id'])
        c.execute("SELECT * FROM business_google_drive_connections WHERE business_id=%s AND status='connected'",(business,))
        connection=_row(c,c.fetchone())
        if not connection or connection['version']!=data['connection_version']:
            return {'status':'cancelled','chat_response':'Подключение Google Диска изменилось. Фото осталось в LocalOS.'}
        c.execute('SELECT * FROM photo_assets WHERE id=%s AND business_id=%s',(data['photo_id'],business))
        photo=_row(c,c.fetchone())
        if not photo or (photo.get('asset_version') or 1)!=data['asset_version']:raise ValueError('Версия фото изменилась.')
        from services.media_file_storage import load_media_file
        original=(photo.get('versions_json') or {}).get('original') or {}
        content=load_media_file(original.get('storage_path') or photo.get('storage_key') or '')
        if not content:raise ValueError('Исходное фото недоступно.')
        mime=original.get('mime_type') or photo.get('mime_type')
        if mime not in {'image/jpeg','image/png','image/webp'}:raise ValueError('Поддерживаются только фотографии.')
        headers={'Authorization':'Bearer '+access_token(connection)}
        created=photo.get('created_at') or datetime.now(timezone.utc)
        folder=f'LocalOS/{business}/{created:%Y-%m-%d}'
        parent=None;path=''
        for name in folder.split('/'):
            path=path+'/'+name
            identifier=remote_id(c,db.conn,business,connection['version'],path,headers)
            ensure_file(identifier,name,parent,headers);parent=identifier
        extension={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[mime]
        name=f"{data['photo_id']}-v{data['asset_version']}"+extension
        identifier=remote_id(c,db.conn,business,connection['version'],path+'/'+name,headers)
        operator_workday.authorize(c,business,job['user_id'])
        ensure_file(identifier,name,parent,headers,content,mime)
        c.execute("UPDATE photo_google_drive_sync SET status='synced',remote_path=%s,error_code=NULL,updated_at=NOW() WHERE photo_asset_id=%s AND asset_version=%s AND connection_version=%s",(identifier,*key))
        db.conn.commit()
        return {'status':'completed','chat_response':'Фото сохранено на Google Диске.','photo_id':data['photo_id']}
    except Exception:
        import sys
        reconnect=isinstance(sys.exception(),ReconnectRequired)
        db.conn.rollback()
        if reconnect:
            c.execute("UPDATE business_google_drive_connections SET status='needs_reconnect',updated_at=NOW() WHERE business_id=%s AND version=%s",(business,data['connection_version']))
        c.execute("UPDATE photo_google_drive_sync SET status='needs_retry',error_code='sync_failed',updated_at=NOW() WHERE photo_asset_id=%s AND asset_version=%s AND connection_version=%s",key)
        db.conn.commit()
        raise ValueError('Синхронизация с Google Диском не завершена. Фото сохранено в LocalOS.') from None
    finally:
        if locked:
            db.conn.rollback()
            c.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))',('google-drive:'+business,))
            db.conn.commit()
        db.close()
