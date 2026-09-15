"""Narrow, server-owned endpoints for reading an explicitly connected media folder."""
import hashlib
import json
import re
from urllib.parse import urlparse,quote
import requests
from auth_encryption import encrypt_auth_data,decrypt_auth_data
from services.operator_conversations import _row
from services import storage_oauth_settings,yandex_disk

GOOGLE='https://www.googleapis.com/drive/v3'
FOLDER='application/vnd.google-apps.folder'
MAX_BYTES=10*1024*1024


class AccessLost(ValueError):
    pass


def google_settings(cursor):
    cursor.execute("SELECT client_email,version FROM disk_import_credentials WHERE id='google_reader'")
    row=_row(cursor,cursor.fetchone())
    return {'configured':bool(row),'client_email':row.get('client_email',''),'version':row.get('version',0)}


def save_google_settings(cursor,user,payload):
    storage_oauth_settings.authorize(cursor,user)
    if not storage_oauth_settings.encryption_ready():raise ValueError('Шифрование не настроено.')
    info=payload.get('credentials')
    if not isinstance(info,dict) or info.get('type')!='service_account':raise ValueError('Выберите JSON-ключ служебного аккаунта Google.')
    email=info.get('client_email','')
    if not isinstance(email,str) or not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com',email):raise ValueError('Некорректный адрес служебного аккаунта.')
    # Ignore arbitrary endpoints from uploaded JSON. Never permit domain-wide delegation.
    safe={key:info.get(key) for key in ('type','project_id','private_key_id','private_key','client_email','client_id')}
    safe['token_uri']='https://oauth2.googleapis.com/token'
    from google.oauth2.service_account import Credentials
    try:Credentials.from_service_account_info(safe,scopes=['https://www.googleapis.com/auth/drive.readonly'])
    except Exception:raise ValueError('Некорректный закрытый ключ Google.') from None
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('disk-import-credentials',0))")
    current=google_settings(cursor)
    if payload.get('version')!=current['version']:raise ValueError('Настройки изменились. Обновите страницу.')
    if current['client_email'] and current['client_email']!=email:
        cursor.execute("SELECT id FROM disk_import_sources WHERE provider='google' AND state!='disconnected' LIMIT 1")
        if cursor.fetchone():raise ValueError('Сначала отключите папки от прежнего служебного аккаунта.')
    cursor.execute('''INSERT INTO disk_import_credentials(id,client_email,secret_encrypted,updated_by) VALUES ('google_reader',%s,%s,%s)
        ON CONFLICT(id) DO UPDATE SET client_email=EXCLUDED.client_email,secret_encrypted=EXCLUDED.secret_encrypted,
        updated_by=EXCLUDED.updated_by,version=disk_import_credentials.version+1,updated_at=NOW()''',(email,encrypt_auth_data(json.dumps(safe)),user))
    return google_settings(cursor)


def google_folder_id(value):
    if not isinstance(value,str):raise ValueError('Вставьте ссылку на папку Google Диска.')
    parsed=urlparse(value)
    match=re.fullmatch(r'/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)(?:/)?',parsed.path)
    if parsed.scheme!='https' or parsed.hostname!='drive.google.com' or parsed.username or parsed.password or not match:
        raise ValueError('Нужна ссылка https://drive.google.com/drive/folders/…')
    return match.group(1)


def checked(response):
    if response.status_code in {401,403,404}:raise AccessLost('Доступ к папке или файлу отсутствует.')
    if response.status_code!=200:raise ValueError('Диск временно недоступен. Проверка будет повторена.')
    return response.json()


def numeric(value):
    if isinstance(value,str) and re.fullmatch(r'(0|[1-9][0-9]{0,15})',value):return json.loads(value)
    return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else 0


def kind(mime,name):
    if mime in {'video/mp4','video/quicktime','video/webm'}:return 'video'
    if mime in {'image/jpeg','image/png','image/webp','image/heic','image/heif'}:return 'photo'
    return 'unsupported'


def bounded_download(response):
    try:
        if response.status_code in {401,403,404}:raise AccessLost('Нет доступа к фотографии.')
        if response.status_code!=200:raise ValueError('Не удалось скачать фотографию.')
        content=bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content)>MAX_BYTES:raise ValueError('photo_too_large')
        return bytes(content)
    finally:response.close()


class GoogleReader:
    def __init__(self,cursor,source):
        cursor.execute("SELECT * FROM disk_import_credentials WHERE id='google_reader'")
        row=_row(cursor,cursor.fetchone())
        if not row or row['client_email']!=source['credential_identity']:raise AccessLost('Служебный аккаунт изменился. Подключите папку заново.')
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import Request
        credentials=Credentials.from_service_account_info(json.loads(decrypt_auth_data(row['secret_encrypted'])),scopes=['https://www.googleapis.com/auth/drive.readonly'])
        from google.auth.exceptions import RefreshError
        try:credentials.refresh(Request())
        except RefreshError:raise AccessLost('Ключ служебного аккаунта недействителен.') from None
        self.headers={'Authorization':'Bearer '+credentials.token};self.source=source

    def metadata(self,identifier):
        return checked(requests.get(GOOGLE+'/files/'+quote(identifier,safe=''),headers=self.headers,
            params={'fields':'id,name,mimeType,parents,md5Checksum,modifiedTime,size,trashed,videoMediaMetadata,capabilities(canListChildren)','supportsAllDrives':'true'},timeout=(10,30)))

    def inside(self,identifier):
        visited=set()
        while identifier!=self.source['root_id']:
            if identifier in visited or len(visited)>=64:raise AccessLost('Папка находится за пределами источника.')
            visited.add(identifier);row=self.metadata(identifier)
            if row.get('trashed') or not row.get('parents'):raise AccessLost('Файл находится за пределами подключённой папки.')
            identifier=row['parents'][0]

    def page(self,folder,token=None):
        self.inside(folder)
        metadata=self.metadata(folder)
        if metadata.get('mimeType')!=FOLDER or metadata.get('trashed') or metadata.get('capabilities',{}).get('canListChildren') is False:
            raise AccessLost('Исходная папка недоступна.')
        body=checked(requests.get(GOOGLE+'/files',headers=self.headers,params={'q':"'"+folder+"' in parents and trashed = false",
            'pageSize':100,'pageToken':token or '', 'fields':'incompleteSearch,nextPageToken,files(id,name,mimeType,parents,md5Checksum,modifiedTime,size,videoMediaMetadata)',
            'supportsAllDrives':'true','includeItemsFromAllDrives':'true'},timeout=(10,30)))
        if body.get('incompleteSearch') or not isinstance(body.get('files'),list):raise ValueError('Диск вернул неполный результат поиска.')
        return [self.normalize(row) for row in body['files']],body.get('nextPageToken')

    def normalize(self,row):
        mime=row.get('mimeType','');identifier=row['id']
        return {'id':identifier,'name':row.get('name',''),'mime_type':mime,'kind':'folder' if mime==FOLDER else kind(mime,row.get('name','')),
            'revision':row.get('md5Checksum') or row.get('modifiedTime') or identifier,'size':numeric(row.get('size',0)),
            'duration_ms':numeric((row.get('videoMediaMetadata') or {}).get('durationMillis')),
            'url':'https://drive.google.com/'+('drive/folders/' if mime==FOLDER else 'file/d/')+identifier+('' if mime==FOLDER else '/view')}

    def validate_file(self,file):
        self.inside(file['id']);current=self.normalize(self.metadata(file['id']))
        if current['revision']!=file['revision']:raise ValueError('Файл изменился во время импорта.')

    def download(self,file):
        self.validate_file(file)
        return bounded_download(requests.get(GOOGLE+'/files/'+quote(file['id'],safe=''),params={'alt':'media','supportsAllDrives':'true'},headers=self.headers,stream=True,timeout=(10,60),allow_redirects=False))


class YandexReader:
    def __init__(self,cursor,source):
        cursor.execute("SELECT * FROM business_disk_connections WHERE business_id=%s AND status='connected'",(source['business_id'],))
        row=_row(cursor,cursor.fetchone())
        if not row or str(row['version'])!=source['credential_identity']:raise AccessLost('Подключите Яндекс Диск заново.')
        self.headers={'Authorization':'OAuth '+decrypt_auth_data(row['token_encrypted'])};self.source=source

    def metadata(self,path):
        return checked(requests.get(yandex_disk.API+'/resources',params={'path':path,'limit':1},headers=self.headers,timeout=(10,30)))

    def page(self,folder,token=None):
        root=self.source['root_id']
        if folder!=root and not folder.startswith(root+'/'):raise AccessLost('Папка находится за пределами источника.')
        body=checked(requests.get(yandex_disk.API+'/resources',params={'path':folder,'offset':token or 0,'limit':100,'sort':'name'},headers=self.headers,timeout=(10,30)))
        embedded=body.get('_embedded')
        if not isinstance(embedded,dict):raise AccessLost('Исходная папка недоступна.')
        rows=embedded.get('items',[])
        offset=embedded.get('offset',0)+len(rows)
        if offset<embedded.get('total',0) and not rows:raise ValueError('Диск вернул незавершённую страницу.')
        return [self.normalize(row,folder) for row in rows],offset if offset<embedded.get('total',0) else None

    def normalize(self,row,parent=None):
        path=parent+'/'+row['name'] if parent else row.get('path','');mime=row.get('mime_type','')
        return {'id':row.get('resource_id') or path,'name':row.get('name',''),'path':path,'mime_type':mime,
            'kind':'folder' if row.get('type')=='dir' else kind(mime,row.get('name','')),
            'revision':row.get('sha256') or row.get('md5') or row.get('modified') or path,'size':numeric(row.get('size',0)),
            'url':'https://disk.yandex.ru/client/disk/'+quote(row.get('path','').removeprefix('disk:/'),safe='/')}

    def validate_file(self,file):
        root=self.source['root_id']
        if not file['path'].startswith(root+'/'):raise AccessLost('Фото за пределами папки.')
        current=self.metadata(file['path'])
        if self.normalize(current,file['path'].rsplit('/',1)[0])['revision']!=file['revision'] or (current.get('resource_id') and current['resource_id']!=file['id']):raise ValueError('Фото изменилось во время импорта.')

    def download(self,file):
        self.validate_file(file)
        data=checked(requests.get(yandex_disk.API+'/resources/download',params={'path':file['path']},headers=self.headers,timeout=(10,30)))
        url=yandex_disk.provider_href(data.get('href',''))
        return bounded_download(requests.get(url,stream=True,timeout=(10,60),allow_redirects=False))


def reader(cursor,source):
    return GoogleReader(cursor,source) if source['provider']=='google' else YandexReader(cursor,source)
