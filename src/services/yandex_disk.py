"""Private app-folder sync; media assets remain the content-plan source of truth."""
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import requests
from auth_encryption import encrypt_auth_data, decrypt_auth_data
from database_manager import DatabaseManager
from services.operator_conversations import _row
from services import operator_workday

API='https://cloud-api.yandex.net/v1/disk'


def configuration():
    import auth_encryption
    if not auth_encryption.CRYPTOGRAPHY_AVAILABLE or not os.getenv('EXTERNAL_AUTH_SECRET_KEY','').strip():
        raise ValueError('Шифрование подключения Диска не настроено оператором LocalOS.')
    client=os.getenv('YANDEX_DISK_CLIENT_ID','')
    secret=os.getenv('YANDEX_DISK_CLIENT_SECRET','')
    redirect=os.getenv('YANDEX_DISK_REDIRECT_URI','https://localos.pro/api/operator/disk/callback')
    if not client or not secret:raise ValueError('Подключение Яндекс Диска ещё не настроено оператором LocalOS.')
    return client,secret,redirect


def status(cursor,business):
    cursor.execute('SELECT status,version,updated_at FROM business_disk_connections WHERE business_id=%s',(business,))
    connection=_row(cursor,cursor.fetchone())
    cursor.execute('SELECT status,COUNT(*) count FROM photo_disk_sync WHERE business_id=%s GROUP BY status',(business,))
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
    cursor.execute("INSERT INTO business_disk_oauth_states(state_hash,business_id,user_id,expires_at) VALUES (%s,%s,%s,NOW()+INTERVAL '10 minutes')",
        (hashlib.sha256(state.encode()).hexdigest(),business,user))
    return {'url':'https://oauth.yandex.ru/authorize?'+urlencode({'response_type':'code','client_id':client,'redirect_uri':redirect,
            'scope':'cloud_api:disk.app_folder','state':state})}


def finish(cursor,state,code):
    client,secret,redirect=configuration()
    cursor.execute('SELECT * FROM business_disk_oauth_states WHERE state_hash=%s AND used_at IS NULL AND expires_at>NOW() FOR UPDATE',
                   (hashlib.sha256(state.encode()).hexdigest(),))
    row=_row(cursor,cursor.fetchone())
    if not row:raise ValueError('Ссылка подключения истекла или уже использована. Начните подключение заново.')
    operator_workday.authorize(cursor,row['business_id'],row['user_id'],owner=True)
    response=requests.post('https://oauth.yandex.ru/token',data={'grant_type':'authorization_code','code':code,
        'client_id':client,'client_secret':secret,'redirect_uri':redirect},timeout=(10,30))
    body=response.json()
    if response.status_code!=200 or not body.get('access_token'):
        raise ValueError('Яндекс не подтвердил подключение. Начните подключение заново.')
    token=body['access_token']
    check=requests.get(API+'/resources',params={'path':'app:/'},headers={'Authorization':'OAuth '+token},timeout=(10,30))
    if check.status_code!=200:raise ValueError('Нет доступа к папке приложения на Диске.')
    cursor.execute('''INSERT INTO business_disk_connections(business_id,token_encrypted,connected_by)
        VALUES (%s,%s,%s) ON CONFLICT(business_id) DO UPDATE SET token_encrypted=EXCLUDED.token_encrypted,
        connected_by=EXCLUDED.connected_by,status='connected',version=business_disk_connections.version+1,updated_at=NOW()''',
        (row['business_id'],encrypt_auth_data(token),row['user_id']))
    cursor.execute('UPDATE business_disk_oauth_states SET used_at=NOW() WHERE state_hash=%s',(row['state_hash'],))
    return row['business_id'],row['user_id']


def disconnect(cursor,business,user):
    operator_workday.authorize(cursor,business,user,owner=True)
    cursor.execute("UPDATE business_disk_connections SET token_encrypted=NULL,status='disconnected',version=version+1,updated_at=NOW() WHERE business_id=%s",(business,))
    return {'success':True}


def queue(cursor,business,user,photo_id):
    operator_workday.authorize(cursor,business,user)
    cursor.execute("SELECT version FROM business_disk_connections WHERE business_id=%s AND status='connected'",(business,))
    connection=_row(cursor,cursor.fetchone())
    if not connection:return {'status':'local_only'}
    cursor.execute('SELECT asset_version FROM photo_assets WHERE id=%s AND business_id=%s',(photo_id,business))
    photo=_row(cursor,cursor.fetchone())
    if not photo:raise PermissionError('Фото недоступно.')
    version=photo.get('asset_version') or 1
    cursor.execute('''INSERT INTO photo_disk_sync(photo_asset_id,business_id,asset_version,connection_version)
        VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(photo_id,business,version,connection['version']))
    from services.operator_async_jobs import create_operator_async_job
    key=f"disk:{business}:{photo_id}:{version}:{connection['version']}"
    job=create_operator_async_job(cursor,user_id=user,business_id=business,action_id=None,kind='yandex_disk_sync',
        payload={'photo_id':photo_id,'asset_version':version,'connection_version':connection['version']},idempotency_key=key,stage='Сохраняю фото на Диске',max_attempts=3)
    return {'status':'queued','job_id':job['id']}


def queue_operator_photos(cursor,business,user):
    cursor.execute("SELECT DISTINCT photo_asset_id FROM operator_attachments WHERE business_id=%s AND purpose='content' AND photo_asset_id IS NOT NULL LIMIT 1000",(business,))
    ids=[_row(cursor,row)['photo_asset_id'] for row in cursor.fetchall()]
    for identifier in ids:queue(cursor,business,user,identifier)
    return len(ids)


def provider_href(value):
    url=urlparse(value)
    host=url.hostname or ''
    if url.scheme!='https' or url.username or url.password or url.port not in {None,443} or not any(host.endswith('.'+suffix) for suffix in ('yandex.net','yandex.ru')):
        raise ValueError('Некорректный адрес загрузки от Яндекс Диска.')
    return value


def process_job(job):
    db=DatabaseManager();c=db.conn.cursor();business=job['business_id'];data=job['payload_json']
    key=(data['photo_id'],data['asset_version'],data['connection_version'])
    try:
        operator_workday.authorize(c,business,job['user_id'])
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('disk-sync:'+business+':'+data['photo_id'],))
        c.execute("SELECT * FROM business_disk_connections WHERE business_id=%s AND status='connected' FOR SHARE",(business,))
        connection=_row(c,c.fetchone())
        if not connection or connection['version']!=data['connection_version']:
            return {'status':'cancelled','chat_response':'Подключение Диска изменилось. Фото сохранено в LocalOS.'}
        c.execute('SELECT * FROM photo_assets WHERE id=%s AND business_id=%s',(data['photo_id'],business))
        photo=_row(c,c.fetchone())
        if not photo or (photo.get('asset_version') or 1)!=data['asset_version']:
            raise ValueError('Версия фото изменилась. Повторите синхронизацию актуального фото.')
        from services.media_file_storage import load_media_file
        original=(photo.get('versions_json') or {}).get('original') or {}
        content=load_media_file(original.get('storage_path') or photo.get('storage_key') or '')
        if not content:raise ValueError('Исходное фото недоступно в LocalOS.')
        token=decrypt_auth_data(connection['token_encrypted'])
        headers={'Authorization':'OAuth '+token}
        created=photo.get('created_at') or datetime.now(timezone.utc)
        folder=f"app:/LocalOS/{business}/{created:%Y/%m}"
        extension={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}.get(original.get('mime_type') or photo.get('mime_type'),'.jpg')
        path=folder+f"/{data['photo_id']}-v{data['asset_version']}"+extension
        parts=folder.split('/')
        for length in range(2,len(parts)+1):
            response=requests.put(API+'/resources',params={'path':'/'.join(parts[:length])},headers=headers,timeout=(10,30))
            if response.status_code not in {201,409}:raise ValueError('Не удалось создать папку на Диске.')
        digest=hashlib.md5(content).hexdigest()
        existing=requests.get(API+'/resources',params={'path':path},headers=headers,timeout=(10,30))
        if existing.status_code==200 and existing.json().get('md5')!=digest:
            raise ValueError('Файл на Диске отличается. Автоматическая перезапись отключена.')
        if existing.status_code!=200:
            if existing.status_code!=404:raise ValueError('Диск недоступен. Фото осталось в LocalOS.')
            upload=requests.get(API+'/resources/upload',params={'path':path,'overwrite':'false'},headers=headers,timeout=(10,30))
            if upload.status_code!=200:raise ValueError('Не удалось подготовить загрузку на Диск.')
            destination=provider_href(upload.json().get('href',''))
            sent=requests.put(destination,data=content,timeout=(10,60),allow_redirects=False)
            if sent.status_code not in {201,202}:raise ValueError('Не удалось загрузить фото на Диск.')
            verify=requests.get(API+'/resources',params={'path':path},headers=headers,timeout=(10,30))
            if verify.status_code!=200 or verify.json().get('md5')!=digest:
                raise ValueError('Диск ещё не подтвердил сохранение файла. Можно повторить проверку.')
        c.execute("UPDATE photo_disk_sync SET status='synced',remote_path=%s,error_code=NULL,updated_at=NOW() WHERE photo_asset_id=%s AND asset_version=%s AND connection_version=%s",(path,*key))
        db.conn.commit()
        return {'status':'completed','chat_response':'Фото сохранено на Яндекс Диске.','photo_id':data['photo_id']}
    except Exception:
        db.conn.rollback()
        c.execute("UPDATE photo_disk_sync SET status='needs_retry',error_code='sync_failed',updated_at=NOW() WHERE photo_asset_id=%s AND asset_version=%s AND connection_version=%s",key)
        db.conn.commit()
        raise ValueError('Синхронизация с Диском не завершена. Фото сохранено в LocalOS.') from None
    finally:
        db.close()
