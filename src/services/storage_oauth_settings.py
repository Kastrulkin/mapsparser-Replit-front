"""Platform admin settings. Never return stored client secrets to the browser."""
import os
from auth_encryption import encrypt_auth_data, decrypt_auth_data
from database_manager import DatabaseManager
from services.operator_conversations import _row

PROVIDERS={
    'yandex':{'prefix':'YANDEX_DISK','name':'Яндекс Диск','callback':'disk'},
    'google':{'prefix':'GOOGLE_DRIVE','name':'Google Диск','callback':'google-drive'},
}


def provider_info(provider):
    if not isinstance(provider,str) or provider not in PROVIDERS:raise ValueError('Неизвестное хранилище.')
    return PROVIDERS[provider]


def encryption_ready():
    import auth_encryption
    return auth_encryption.CRYPTOGRAPHY_AVAILABLE and bool(os.getenv('EXTERNAL_AUTH_SECRET_KEY','').strip())


def environment(provider):
    info=provider_info(provider);prefix=info['prefix']
    return (os.getenv(prefix+'_CLIENT_ID','').strip(),os.getenv(prefix+'_CLIENT_SECRET','').strip(),
            os.getenv(prefix+'_REDIRECT_URI','').strip() or 'https://localos.pro/api/operator/'+info['callback']+'/callback')


def configuration(provider,cursor=None):
    if not encryption_ready():raise ValueError('Шифрование подключений не настроено в LocalOS.')
    client,secret,redirect=environment(provider)
    db=None
    try:
        if cursor is None:
            db=DatabaseManager();cursor=db.conn.cursor()
        cursor.execute('SELECT client_id,secret_encrypted FROM storage_oauth_apps WHERE provider=%s',(provider,))
        row=_row(cursor,cursor.fetchone())
        if row:client,secret=row['client_id'],decrypt_auth_data(row['secret_encrypted'])
    finally:
        if db is not None:db.close()
    if not client or not secret:raise ValueError('Подключение '+provider_info(provider)['name']+' ещё не настроено в LocalOS.')
    return client,secret,redirect


def authorize(cursor,user):
    cursor.execute('SELECT id FROM users WHERE id=%s AND is_active=TRUE AND is_superadmin=TRUE',(user,))
    if not cursor.fetchone():raise PermissionError('Настройки доступны только администратору LocalOS.')


def public_settings(cursor):
    items=[]
    for provider,info in PROVIDERS.items():
        cursor.execute('SELECT client_id,secret_encrypted,version,updated_at FROM storage_oauth_apps WHERE provider=%s',(provider,))
        row=_row(cursor,cursor.fetchone());client,secret,redirect=environment(provider)
        items.append({'provider':provider,'name':info['name'],'client_id':row.get('client_id',client),
            'secret_saved':bool(row.get('secret_encrypted') or secret),'version':row.get('version',0),
            'redirect_uri':redirect,'source':'interface' if row else 'environment',
            'updated_at':row.get('updated_at')})
    return {'items':items,'encryption_ready':encryption_ready()}


def save(cursor,user,payload):
    authorize(cursor,user)
    if not isinstance(payload,dict):raise ValueError('Ожидается объект настроек.')
    provider=payload.get('provider');provider_info(provider)
    if not encryption_ready():raise ValueError('Шифрование подключений не настроено в LocalOS.')
    client=payload.get('client_id');secret=payload.get('client_secret','')
    if not isinstance(client,str) or not client.strip() or len(client)>512 or any(ch.isspace() for ch in client):
        raise ValueError('Укажите Client ID без пробелов.')
    if not isinstance(secret,str) or len(secret)>4096 or any(ch.isspace() for ch in secret):raise ValueError('Некорректный Client Secret.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('storage-oauth:'+provider,))
    cursor.execute('SELECT * FROM storage_oauth_apps WHERE provider=%s FOR UPDATE',(provider,))
    row=_row(cursor,cursor.fetchone());old_client,old_secret,_=environment(provider)
    if payload.get('version')!=row.get('version',0):raise ValueError('Настройки изменились. Обновите страницу перед сохранением.')
    old_client=row.get('client_id',old_client)
    if client!=old_client and not secret:raise ValueError('Для нового Client ID укажите Client Secret.')
    if client!=old_client:
        table={'yandex':'business_disk_connections','google':'business_google_drive_connections'}[provider]
        cursor.execute('SELECT COUNT(*) count FROM '+table+" WHERE status IN ('connected','needs_reconnect')")
        if _row(cursor,cursor.fetchone())['count']:raise ValueError('Сначала отключите бизнесы от прежнего OAuth-приложения. Смена Client ID меняет доступ к их файлам.')
    encrypted=encrypt_auth_data(secret) if secret else row.get('secret_encrypted') or encrypt_auth_data(old_secret)
    if not encrypted:raise ValueError('Укажите Client Secret.')
    cursor.execute('''INSERT INTO storage_oauth_apps(provider,client_id,secret_encrypted,updated_by) VALUES (%s,%s,%s,%s)
        ON CONFLICT(provider) DO UPDATE SET client_id=EXCLUDED.client_id,secret_encrypted=EXCLUDED.secret_encrypted,
        updated_by=EXCLUDED.updated_by,version=storage_oauth_apps.version+1,updated_at=NOW()''',(provider,client,encrypted,user))
    return public_settings(cursor)
