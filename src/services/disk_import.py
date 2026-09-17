"""Durable inbound media. No publication, outbound sync, or video download."""
import hashlib
import io
import json
import os
import secrets
import uuid
from datetime import datetime,timezone
from PIL import Image,ImageOps
from database_manager import DatabaseManager
from services.operator_conversations import _row
from services import disk_import_providers


def enabled(business):
    return business in {value.strip() for value in os.getenv('DISK_IMPORT_BUSINESS_IDS','').split(',') if value.strip()}


def authorize(c,business,user,owner=False):
    from services.operator_audio import authorize_actor
    actor,_=authorize_actor(c,user,business,check_subscription=False)
    if not enabled(business):raise PermissionError('Импорт материалов пока отключён для бизнеса.')
    is_owner=actor.get('role')=='business_owner' or bool(actor.get('is_superadmin'))
    if owner and not is_owner:raise PermissionError('Папку подключает владелец бизнеса.')
    return is_owner


def load(c,business,source_id):
    c.execute('SELECT * FROM disk_import_sources WHERE id=%s AND business_id=%s FOR UPDATE',(source_id,business))
    source=_row(c,c.fetchone())
    if not source:raise PermissionError('Источник недоступен.')
    return source


def public(source):
    return {key:source.get(key) for key in ('id','provider','root_name','root_url','version','state','last_checked_at','error_code','scan_id')}


def status(c,business,user):
    owner=authorize(c,business,user)
    c.execute("SELECT * FROM disk_import_sources WHERE business_id=%s AND state!='disconnected' ORDER BY created_at",(business,))
    sources=[public(_row(c,row)) for row in c.fetchall()]
    for source in sources:
        c.execute('SELECT status,error_code,COUNT(*) count FROM disk_import_files WHERE source_id=%s GROUP BY status,error_code',(source['id'],))
        source['counts']=[_row(c,row) for row in c.fetchall()]
    return {'enabled':True,'can_configure':owner,'sources':sources,'google':disk_import_providers.google_settings(c) if owner else None}


def prepare(c,business,user,payload):
    authorize(c,business,user,owner=True);provider=payload.get('provider')
    if provider not in {'google','yandex'}:raise ValueError('Выберите Яндекс Диск или Google Диск.')
    c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('disk-import-setup:'+business+':'+provider,))
    c.execute("SELECT * FROM disk_import_sources WHERE business_id=%s AND provider=%s AND state!='disconnected' FOR UPDATE",(business,provider))
    existing=_row(c,c.fetchone())
    if existing and existing['state']!='awaiting_proof':raise ValueError('Источник уже подключён. Сначала отключите его.')
    identifier=existing.get('id') or str(uuid.uuid4());challenge=None;challenge_hash=None
    if provider=='google':
        info=disk_import_providers.google_settings(c)
        if not info['configured']:raise ValueError('Администратор LocalOS ещё не настроил чтение Google Диска.')
        root=disk_import_providers.google_folder_id(payload.get('folder_url'));identity=info['client_email'];state='awaiting_proof'
        # Folder metadata is not exposed before the ownership proof.
        name='Папка Google Диска';url='https://drive.google.com/drive/folders/'+root
        challenge='LocalOS-'+secrets.token_hex(16);challenge_hash=hashlib.sha256(challenge.encode()).hexdigest()
    else:
        c.execute("SELECT version FROM business_disk_connections WHERE business_id=%s AND status='connected'",(business,))
        connection=_row(c,c.fetchone())
        if not connection:raise ValueError('Сначала подключите Яндекс Диск в Операторе.')
        identity=str(connection['version']);root='app:/LocalOS/'+business+'/Входящие';state='ready'
        stub={'business_id':business,'credential_identity':identity,'root_id':root}
        client=disk_import_providers.YandexReader(c,stub)
        from services import yandex_disk
        import requests
        parts=root.split('/')
        for count in range(2,len(parts)+1):
            response=requests.put(yandex_disk.API+'/resources',params={'path':'/'.join(parts[:count])},headers=client.headers,timeout=(10,30))
            if response.status_code not in {201,409}:raise ValueError('Не удалось создать входящую папку.')
        metadata=client.metadata(root);name=metadata.get('name') or 'Входящие'
        url=client.normalize(metadata)['url']
    c.execute('''INSERT INTO disk_import_sources(id,business_id,provider,root_id,root_name,root_url,connected_by,credential_identity,state,challenge_hash,challenge_expires_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()+INTERVAL '30 minutes')
        ON CONFLICT(id) DO UPDATE SET root_id=EXCLUDED.root_id,root_url=EXCLUDED.root_url,connected_by=EXCLUDED.connected_by,
        credential_identity=EXCLUDED.credential_identity,challenge_hash=EXCLUDED.challenge_hash,challenge_expires_at=EXCLUDED.challenge_expires_at,
        challenge_used_at=NULL,version=disk_import_sources.version+1,updated_at=NOW() RETURNING *''',
        (identifier,business,provider,root,name,url,user,identity,state,challenge_hash))
    result=public(_row(c,c.fetchone()))
    if challenge:result['proof_folder_name']=challenge
    return result


def verify(c,business,user,payload):
    authorize(c,business,user,owner=True);source=load(c,business,payload.get('source_id'))
    code=payload.get('code','')
    if not isinstance(code,str) or source['state']!='awaiting_proof' or source['challenge_used_at'] or not source['challenge_expires_at'] or source['challenge_expires_at']<=datetime.now(timezone.utc) or not secrets.compare_digest(hashlib.sha256(code.encode()).hexdigest(),source.get('challenge_hash') or ''):
        raise ValueError('Код истёк или уже использован. Подготовьте подключение заново.')
    client=disk_import_providers.reader(c,source)
    # Exact direct-child query avoids leaking the source listing before proof.
    import requests
    body=disk_import_providers.checked(requests.get(disk_import_providers.GOOGLE+'/files',headers=client.headers,
        params={'q':"'"+source['root_id']+"' in parents and name = '"+code+"' and mimeType = '"+disk_import_providers.FOLDER+"' and trashed = false",
                'pageSize':2,'fields':'files(id)','supportsAllDrives':'true','includeItemsFromAllDrives':'true'},timeout=(10,30)))
    if not body.get('files'):raise ValueError('Создайте в выбранной папке подпапку с выданным кодом.')
    contents,continuation=client.page(body['files'][0]['id'])
    if contents or continuation is not None:raise ValueError('Подпапка подтверждения должна быть пустой.')
    metadata=client.metadata(source['root_id'])
    if metadata.get('mimeType')!=disk_import_providers.FOLDER or metadata.get('trashed') or metadata.get('capabilities',{}).get('canListChildren') is False:
        raise ValueError('Нужен доступ Читатель к содержимому папки.')
    c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('disk-import-root:'+source['root_id'],))
    c.execute("SELECT id FROM disk_import_sources WHERE provider='google' AND root_id=%s AND id!=%s AND state NOT IN ('disconnected','awaiting_proof')",(source['root_id'],source['id']))
    if c.fetchone():raise ValueError('Эта папка уже подключена к другому источнику.')
    c.execute("UPDATE disk_import_sources SET state='ready',root_name=%s,challenge_used_at=NOW(),challenge_hash=NULL,version=version+1 WHERE id=%s RETURNING *",(metadata.get('name','Папка Google Диска'),source['id']))
    return public(_row(c,c.fetchone()))


def enqueue_scan(c,source):
    from services.operator_async_jobs import create_operator_async_job
    if not source.get('scan_id'):
        source['scan_id']=str(uuid.uuid4());source['scan_sequence']=0
        c.execute("UPDATE disk_import_sources SET scan_id=%s,scan_sequence=0,pending_json=%s,visited_json=%s WHERE id=%s",(source['scan_id'],json.dumps([{'id':source['root_id'],'token':None}]),json.dumps([source['root_id']]),source['id']))
    return create_operator_async_job(c,user_id=source['connected_by'],business_id=source['business_id'],action_id=None,kind='disk_import_scan',
        payload={'source_id':source['id'],'version':source['version'],'scan_id':source['scan_id'],'sequence':source['scan_sequence']},
        idempotency_key=f"disk-scan:{source['id']}:{source['version']}:{source['scan_id']}:{source['scan_sequence']}",stage='Проверяю папку с материалами',max_attempts=5)


def action(c,business,user,payload):
    authorize(c,business,user,owner=True);source=load(c,business,payload.get('source_id'))
    if source['version']!=payload.get('version'):raise ValueError('Состояние источника изменилось. Обновите страницу.')
    command=payload.get('action')
    allowed={'enable':{'ready'},'pause':{'active','needs_reconnect'},'resume':{'paused','needs_reconnect'},'disconnect':{'ready','awaiting_proof','active','paused','needs_reconnect'},'scan':{'active'}}
    if command not in allowed or source['state'] not in allowed[command]:raise ValueError('Это действие недоступно для текущего состояния.')
    if command in {'enable','resume'}:
        client=disk_import_providers.reader(c,source);client.page(source['root_id'])
    state='active' if command in {'enable','resume','scan'} else 'paused' if command=='pause' else 'disconnected'
    c.execute("UPDATE disk_import_sources SET state=%s,version=version+1,scan_id=NULL,pending_json='[]',visited_json='[]',error_code=NULL,next_scan_at=NOW(),connected_by=%s,updated_at=NOW() WHERE id=%s RETURNING *",(state,user,source['id']))
    source=_row(c,c.fetchone())
    if state=='active':enqueue_scan(c,source)
    if state=='disconnected':refresh_availability(c,business)
    return public(source)


def schedule_due():
    if not os.getenv('DISK_IMPORT_BUSINESS_IDS','').strip():return
    db=DatabaseManager()
    try:
        c=db.conn.cursor()
        c.execute("SELECT * FROM disk_import_sources WHERE state='active' AND next_scan_at<=NOW() ORDER BY next_scan_at FOR UPDATE SKIP LOCKED LIMIT 20")
        rows=[_row(c,row) for row in c.fetchall()]
        for source in rows:
            if not enabled(source['business_id']):continue
            # A failed scan is resumed at its durable page by explicit owner action or next scheduled run.
            job=enqueue_scan(c,source)
            if job.get('status')=='failed':
                c.execute("UPDATE operator_async_jobs SET status='queued',attempt_count=0,next_attempt_at=NOW(),completed_at=NULL WHERE id=%s",(job['id'],))
            c.execute("UPDATE disk_import_sources SET next_scan_at=NOW()+INTERVAL '5 minutes' WHERE id=%s",(source['id'],))
        db.conn.commit()
    finally:db.close()


def refresh_availability(c,business):
    c.execute("""UPDATE photo_assets p SET metadata_json=jsonb_set(COALESCE(metadata_json,'{}'),'{disk_import_available}',
        to_jsonb(EXISTS(SELECT 1 FROM disk_import_files f JOIN disk_import_sources s ON s.id=f.source_id
          WHERE s.business_id=%s AND s.state!='disconnected' AND f.photo_asset_id=p.id AND f.available=TRUE AND f.imported_revision=f.revision)))
        WHERE p.business_id=%s AND p.metadata_json->>'origin'='disk_import' """,(business,business))
    c.execute('''UPDATE external_video_assets v SET available=EXISTS(SELECT 1 FROM disk_import_files f JOIN disk_import_sources s ON s.id=f.source_id
        WHERE s.state!='disconnected' AND f.video_id=v.id AND f.available=TRUE AND f.imported_revision=f.revision) WHERE v.business_id=%s''',(business,))


def process_scan(c,source,data):
    if source['scan_id']!=data['scan_id'] or source['scan_sequence']!=data['sequence']:return {'status':'stale'}
    client=disk_import_providers.reader(c,source)
    pending=source['pending_json'];visited=source['visited_json'];page=pending[0]
    entries,next_token=client.page(page['id'],page.get('token'))
    from services.operator_async_jobs import create_operator_async_job
    for file in entries:
        if file['kind']=='folder':
            identifier=file.get('path') or file['id']
            if identifier not in visited:
                visited.append(identifier);pending.append({'id':identifier,'token':None})
            continue
        c.execute('''INSERT INTO disk_import_files(source_id,external_id,revision,name,kind,metadata_json,last_seen_scan)
            VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_id,external_id) DO UPDATE SET
            revision=EXCLUDED.revision,name=EXCLUDED.name,kind=EXCLUDED.kind,metadata_json=EXCLUDED.metadata_json,
            last_seen_scan=EXCLUDED.last_seen_scan,available=TRUE,updated_at=NOW() RETURNING *''',
            (source['id'],file['id'],file['revision'],file['name'],file['kind'],json.dumps(file),source['scan_id']))
        row=_row(c,c.fetchone())
        if file['kind']=='unsupported':
            c.execute("UPDATE disk_import_files SET status='skipped',error_code='unsupported_format' WHERE source_id=%s AND external_id=%s",(source['id'],file['id']));continue
        if row.get('video_id') and row.get('imported_revision')==file['revision']:
            c.execute('UPDATE external_video_assets SET name=%s,original_url=%s WHERE id=%s AND business_id=%s',(file['name'],file['url'],row['video_id'],source['business_id']))
        if row.get('imported_revision')!=file['revision']:
            job=create_operator_async_job(c,user_id=source['connected_by'],business_id=source['business_id'],action_id=None,kind='disk_import_file',
                payload={'source_id':source['id'],'version':source['version'],'external_id':file['id'],'revision':file['revision']},
                idempotency_key=f"disk-file:{source['id']}:{source['version']}:{file['id']}:{file['revision']}",stage='Добавляю материал с Диска',max_attempts=5)
            if job.get('status')=='failed':c.execute("UPDATE operator_async_jobs SET status='queued',attempt_count=0,next_attempt_at=NOW(),completed_at=NULL WHERE id=%s",(job['id'],))
    if next_token is None:pending.pop(0)
    else:pending[0]['token']=next_token
    if pending:
        c.execute('UPDATE disk_import_sources SET pending_json=%s,visited_json=%s,scan_sequence=scan_sequence+1,error_code=NULL WHERE id=%s RETURNING *',(json.dumps(pending),json.dumps(visited),source['id']))
        enqueue_scan(c,_row(c,c.fetchone()))
    else:
        # Recheck the root before reconciliation; permission failure is never mass deletion.
        client.page(source['root_id'])
        c.execute('UPDATE disk_import_files SET available=FALSE WHERE source_id=%s AND last_seen_scan!=%s',(source['id'],source['scan_id']))
        c.execute("UPDATE disk_import_sources SET scan_id=NULL,pending_json='[]',visited_json='[]',last_checked_at=NOW(),next_scan_at=NOW()+INTERVAL '5 minutes',error_code=NULL WHERE id=%s",(source['id'],))
    refresh_availability(c,source['business_id'])
    return {'status':'completed','chat_response':'Папка проверена.'}


def normalize_photo(content,name,mime):
    if not content or len(content)>disk_import_providers.MAX_BYTES:raise ValueError('photo_too_large')
    if mime in {'image/heic','image/heif'} or name.lower().endswith(('.heic','.heif')):
        import pillow_heif
        pillow_heif.register_heif_opener()
    picture=Image.open(io.BytesIO(content))
    try:
        if picture.width*picture.height>40000000:raise ValueError('photo_too_many_pixels')
        picture.load()
        actual=Image.MIME.get(picture.format,'')
        if picture.format in {'HEIF','HEIC'}:
            converted=ImageOps.exif_transpose(picture).convert('RGB');buffer=io.BytesIO();converted.save(buffer,format='JPEG',quality=90);converted.close()
            content=buffer.getvalue();name=name.rsplit('.',1)[0]+'.jpg';actual='image/jpeg'
        if actual not in {'image/jpeg','image/png','image/webp'}:raise ValueError('unsupported_format')
        if len(content)>disk_import_providers.MAX_BYTES:raise ValueError('photo_too_large')
        return content,name,actual
    finally:picture.close()


def process_file(c,source,data):
    c.execute('SELECT * FROM disk_import_files WHERE source_id=%s AND external_id=%s FOR UPDATE',(source['id'],data['external_id']))
    row=_row(c,c.fetchone())
    if not row or not row['available'] or row['revision']!=data['revision']:return {'status':'stale'}
    c.execute('SELECT * FROM disk_import_revisions WHERE source_id=%s AND external_id=%s AND revision=%s',(source['id'],row['external_id'],row['revision']))
    revision=_row(c,c.fetchone());file=row['metadata_json'];business=source['business_id']
    photo_id=revision.get('photo_asset_id');video_id=revision.get('video_id')
    if not revision:
        client=disk_import_providers.reader(c,source)
        if row['kind']=='photo':
            try:
                if disk_import_providers.numeric(file.get('size'))>disk_import_providers.MAX_BYTES:raise ValueError('photo_too_large')
                content=client.download(file)
                try:content,name,mime=normalize_photo(content,file['name'],file['mime_type'])
                except OSError:raise ValueError('invalid_image') from None
            except ValueError:
                import sys
                code=str(sys.exception())
                if code not in {'photo_too_large','photo_too_many_pixels','unsupported_format','invalid_image'}:raise
                c.execute("UPDATE disk_import_files SET status='skipped',error_code=%s WHERE source_id=%s AND external_id=%s",(code,source['id'],file['id']))
                return {'status':'skipped'}
            digest=hashlib.sha256(content).hexdigest()
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('disk-photo:'+business+':'+digest,))
            c.execute('SELECT id FROM photo_assets WHERE business_id=%s AND content_hash=%s LIMIT 1',(business,digest))
            existing=_row(c,c.fetchone())
            if existing:photo_id=existing['id']
            else:
                from services.media_intelligence import create_uploaded_photo_asset
                photo_id=create_uploaded_photo_asset(c,business_id=business,user_id=source['connected_by'],content=content,original_name=name,mime_type=mime,
                    metadata={'origin':'disk_import','disk_import_available':True,'disk_import':{'source_id':source['id'],'external_id':file['id'],'revision':file['revision']}})['id']
        elif row['kind']=='video':
            # Only metadata. Never download videos, generate public links, or emit publication jobs.
            client.validate_file(file)
            video_id=str(uuid.uuid4())
            c.execute('''INSERT INTO external_video_assets(id,business_id,source_id,external_id,revision,name,mime_type,size_bytes,duration_ms,original_url)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(video_id,business,source['id'],file['id'],file['revision'],file['name'],file['mime_type'],file.get('size',0),file.get('duration_ms'),file['url']))
        c.execute('INSERT INTO disk_import_revisions(source_id,external_id,revision,photo_asset_id,video_id) VALUES (%s,%s,%s,%s,%s)',(source['id'],file['id'],file['revision'],photo_id,video_id))
    authorize(c,business,source['connected_by'],owner=True)
    c.execute("UPDATE disk_import_files SET imported_revision=%s,photo_asset_id=%s,video_id=%s,status='imported',error_code=NULL WHERE source_id=%s AND external_id=%s",(row['revision'],photo_id,video_id,source['id'],row['external_id']))
    refresh_availability(c,business)
    return {'status':'completed','chat_response':'Материал добавлен в медиатеку.'}


def process_job(job):
    db=DatabaseManager();c=db.conn.cursor();source=None
    try:
        source=load(c,job['business_id'],job['payload_json']['source_id'])
        if source['state']!='active' or source['version']!=job['payload_json']['version']:return {'status':'cancelled'}
        authorize(c,source['business_id'],source['connected_by'],owner=True)
        result=process_scan(c,source,job['payload_json']) if job['kind']=='disk_import_scan' else process_file(c,source,job['payload_json'])
        db.conn.commit();return result
    except Exception:
        import sys
        lost=isinstance(sys.exception(),(disk_import_providers.AccessLost,PermissionError));db.conn.rollback()
        if source:
            c.execute("UPDATE disk_import_sources SET error_code=%s,state=CASE WHEN %s THEN 'needs_reconnect' ELSE state END WHERE id=%s AND version=%s",('access_lost' if lost else 'retry_pending',lost,source['id'],source['version']))
            db.conn.commit()
        raise ValueError('Не удалось завершить импорт. Уже сохранённые материалы и история не изменены.') from None
    finally:db.close()
