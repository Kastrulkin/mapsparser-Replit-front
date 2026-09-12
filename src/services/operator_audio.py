"""Private, tenant-bound audio preparation. This module never executes commands."""
import json
import logging
import math
import os
import subprocess
import time
import uuid
from pathlib import Path

from core.auth_helpers import verify_business_access
from services.operator_conversations import _row, get_or_create_operator_conversation, find_latest_operator_conversation
from services.operator_async_jobs import create_operator_async_job
from subscription_manager import build_subscription_capabilities, capability_access_payload

MAX_BYTES = 10 * 1024 * 1024
MAX_SECONDS = 120


def authorize_actor(cursor, user_id, business_id):
    cursor.execute('SELECT id, is_active, is_superadmin FROM users WHERE id=%s', (user_id,))
    user = _row(cursor, cursor.fetchone())
    if not user or not user.get('is_active'):
        raise PermissionError('Аккаунт недоступен')
    user['user_id'] = user_id
    allowed, owner = verify_business_access(cursor, business_id, user)
    if not allowed:
        raise PermissionError('Нет доступа к бизнесу')
    cursor.execute('SELECT subscription_tier, subscription_status, subscription_ends_at FROM businesses WHERE id=%s', (business_id,))
    business = _row(cursor, cursor.fetchone())
    access = build_subscription_capabilities(tier=business.get('subscription_tier') or '',
        status=business.get('subscription_status') or '', subscription_ends_at=business.get('subscription_ends_at'),
        is_superadmin=bool(user.get('is_superadmin')))
    if not capability_access_payload(access, 'operator').get('allowed'):
        raise PermissionError('Оператор недоступен на текущем тарифе')
    return {'role': 'business_owner' if owner == user_id else 'business_user',
            'is_superadmin': bool(user.get('is_superadmin')), 'permissions': ['business.access']}, access


def enabled(kind, business_id):
    flag = 'OPERATOR_VOICE_INPUT_ENABLED' if kind == 'transcription' else 'OPERATOR_VOICE_OUTPUT_ENABLED'
    pilots = {value.strip() for value in os.getenv('OPERATOR_VOICE_BUSINESS_IDS', '').split(',') if value.strip()}
    return os.getenv(flag, '').lower() in {'1', 'true'} and business_id in pilots


def audio_root():
    root = Path(os.getenv('OPERATOR_AUDIO_DIR', '/app/operator_audio')).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def private_path(value):
    path = Path(value).resolve()
    if path.parent != audio_root():
        raise PermissionError('Аудиофайл недоступен')
    return path


def load_asset(cursor, asset_id, user_id, business_id=None):
    cursor.execute('SELECT * FROM operator_audio_assets WHERE id=%s AND user_id=%s AND expires_at>NOW()', (asset_id, user_id))
    asset = _row(cursor, cursor.fetchone())
    if not asset or (business_id and asset['business_id'] != business_id):
        raise PermissionError('Запись недоступна или срок хранения истёк')
    authorize_actor(cursor, user_id, asset['business_id'])
    return asset


def reserve_asset(cursor, *, user_id, business_id, channel, conversation_id, kind, request_id, message_id=None, metadata=None):
    authorize_actor(cursor, user_id, business_id)
    if not enabled(kind, business_id):
        raise ValueError('Голосовая функция пока недоступна для этого бизнеса')
    if channel not in {'web', 'telegram_mini_app', 'telegram'} or not request_id or len(request_id) > 200:
        raise ValueError('Неверный канал или идентификатор запроса')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('audio:' + user_id,))
    cursor.execute('SELECT * FROM operator_audio_assets WHERE user_id=%s AND business_id=%s AND channel=%s AND kind=%s AND request_id=%s AND expires_at>NOW()',
                   (user_id,business_id,channel,kind,request_id))
    existing = _row(cursor,cursor.fetchone())
    if existing:
        return existing, False
    cursor.execute('SELECT COUNT(*) FROM operator_audio_assets WHERE user_id=%s AND kind=%s AND created_at>=NOW()-INTERVAL \'24 hours\'', (user_id,kind))
    count = cursor.fetchone()
    count = next(iter(count.values())) if isinstance(count, dict) else count[0]
    limit = 20 if kind == 'transcription' else 40
    if count >= limit:
        raise ValueError('Достигнут суточный лимит голосовых запросов')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(f'operator:{user_id}:{business_id}:{channel}',))
    if not conversation_id:
        conversation_id = find_latest_operator_conversation(cursor,business_id=business_id,user_id=user_id,channel=channel).get('id')
    conversation = get_or_create_operator_conversation(cursor, business_id=business_id,user_id=user_id,channel=channel,
        conversation_id=conversation_id,transport_key=f'chat:{user_id}:{business_id}:{channel}')
    asset_id = str(uuid.uuid4())
    cursor.execute('''INSERT INTO operator_audio_assets (id,user_id,business_id,conversation_id,kind,channel,request_id,message_id,metadata_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *''',
        (asset_id,user_id,business_id,conversation['id'],kind,channel,request_id,message_id,json.dumps(metadata or {})))
    return _row(cursor,cursor.fetchone()), True


def queue_asset(cursor, asset):
    job = create_operator_async_job(cursor,user_id=asset['user_id'],business_id=asset['business_id'],action_id=None,
        kind='audio_' + asset['kind'], payload={'asset_id': asset['id']},idempotency_key='audio:' + asset['id'],
        stage='Распознаю запись' if asset['kind']=='transcription' else 'Готовлю аудио', max_attempts=3)
    cursor.execute('UPDATE operator_audio_assets SET job_id=%s WHERE id=%s', (job['id'],asset['id']))
    return {'asset_id': asset['id'], 'job_id': job['id'], 'conversation_id': asset['conversation_id']}


def create_transcription(cursor, *, content, **kwargs):
    if not content or len(content)>MAX_BYTES:
        raise ValueError('Запись должна быть непустой и не больше 10 МБ')
    asset, created = reserve_asset(cursor,kind='transcription', **kwargs)
    if created:
        path = audio_root() / (asset['id'] + '.input')
        path.write_bytes(content)
        path.chmod(0o600)
        cursor.execute('UPDATE operator_audio_assets SET path=%s WHERE id=%s',(str(path),asset['id']))
    return queue_asset(cursor,asset)


def create_speech(cursor, *, user_id, message_id):
    cursor.execute("SELECT * FROM operatormessages WHERE id=%s AND user_id=%s AND role='operator'",(message_id,user_id))
    message = _row(cursor,cursor.fetchone())
    if not message:
        raise PermissionError('Ответ недоступен')
    cursor.execute('SELECT channel FROM operatorconversations WHERE id=%s',(message['conversation_id'],))
    channel = _row(cursor,cursor.fetchone()).get('channel')
    # One reusable audio per message per UTC day; expired files can be regenerated.
    from datetime import datetime, timezone
    asset, _ = reserve_asset(cursor,user_id=user_id,business_id=message['business_id'],channel=channel,
        conversation_id=message['conversation_id'],kind='speech',request_id=message_id+':'+datetime.now(timezone.utc).date().isoformat(),message_id=message_id)
    return queue_asset(cursor,asset)


def finance_transcription_result(cursor,asset,text):
    from services.finance_daily import enabled
    from services.operator_finance_daily import finance_input
    pending=False
    if enabled(asset['business_id']):
        cursor.execute('SELECT pending_context FROM operatorconversations WHERE id=%s AND user_id=%s AND business_id=%s',(asset['conversation_id'],asset['user_id'],asset['business_id']))
        pending=(_row(cursor,cursor.fetchone()).get('pending_context') or {}).get('capability')=='finance.daily.input'
    return {'asset_id':asset['id'],'transcript':text,'conversation_id':asset['conversation_id'],
            'auto_submit_finance':enabled(asset['business_id']) and (finance_input(text or '') or pending)}


def consume_transcription(cursor, asset_id, user_id, business_id, conversation_id, text):
    asset = load_asset(cursor,asset_id,user_id,business_id)
    if not enabled('transcription',business_id):
        raise ValueError('Голосовой ввод отключён. Напишите команду текстом')
    if asset['kind'] != 'transcription' or asset['conversation_id'] != conversation_id or asset['status'] != 'ready':
        raise ValueError('Расшифровка уже отправлена или недоступна')
    if not text.strip() or len(text)>10000:
        raise ValueError('Проверьте текст команды')
    cursor.execute("SELECT status FROM operator_async_jobs WHERE id=%s FOR UPDATE", (asset['job_id'],))
    if _row(cursor,cursor.fetchone()).get('status') != 'completed':
        raise ValueError('Распознавание не завершено или отменено')
    cursor.execute("UPDATE operator_audio_assets SET corrected_text=%s,status='submitted' WHERE id=%s AND status='ready' RETURNING id",(text,asset_id))
    if not cursor.fetchone():
        raise ValueError('Расшифровка уже отправлена')


def normalize_audio(path, destination):
    try:
        probe = subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','ogg,matroska,webm,mov,mp3,wav','-show_entries','format=duration:stream=codec_type','-of','json',str(path)],capture_output=True,timeout=15,check=True)
        info = json.loads(probe.stdout)
        duration = float(info.get('format',{}).get('duration',0))
        # WebM recordings can lack duration metadata; decode at most limit + 1 s.
        if duration and (not math.isfinite(duration) or duration>MAX_SECONDS):
            raise ValueError('Запись должна быть не длиннее двух минут')
        if any(stream.get('codec_type')!='audio' for stream in info.get('streams',[])):
            raise ValueError('Загрузите аудиозапись')
        subprocess.run(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','ogg,matroska,webm,mov,mp3,wav','-i',str(path),'-t','121','-vn','-ac','1','-ar','48000','-c:a','libopus','-y',str(destination)],capture_output=True,timeout=30,check=True)
        probe = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(destination)],capture_output=True,timeout=10,check=True)
        duration = float(json.loads(probe.stdout)['format']['duration'])
        if not math.isfinite(duration) or duration<=0 or duration>120.1:
            raise ValueError('Запись должна быть не длиннее двух минут')
        return duration
    except (subprocess.SubprocessError, OSError, KeyError, json.JSONDecodeError):
        raise ValueError('Не удалось прочитать аудио. Запишите его заново') from None


def cleanup_audio(cursor):
    cursor.execute("SELECT to_regclass('public.operator_audio_assets')")
    available = cursor.fetchone()
    if not available or not (next(iter(available.values())) if isinstance(available, dict) else available[0]):
        return
    cleanup_orphan_audio()
    cursor.execute('SELECT id,path FROM operator_audio_assets WHERE expires_at<=NOW() AND path IS NOT NULL LIMIT 100')
    for asset in [_row(cursor,row) for row in cursor.fetchall()]:
        private_path(asset['path']).unlink(missing_ok=True)
        cursor.execute("UPDATE operator_audio_assets SET path=NULL,status='expired' WHERE id=%s",(asset['id'],))


def cleanup_orphan_audio():
    root = audio_root()
    cutoff = time.time() - 86400
    for path in root.iterdir():
        if path.is_file() and not path.is_symlink() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)


def process_audio_job(claimed):
    from database_manager import DatabaseManager
    from services.operator_speechkit import SpeechKit
    db = DatabaseManager()
    normalized = None
    started_at = time.monotonic()
    try:
        cursor = db.conn.cursor()
        asset = load_asset(cursor,claimed['payload_json']['asset_id'],claimed['user_id'],claimed['business_id'])
        if not enabled(asset['kind'],asset['business_id']):
            raise ValueError('Голосовая функция отключена')
        if asset['status'] in {'ready','submitted'}:
            return finance_transcription_result(cursor,asset,asset.get('transcript'))
        if asset['status'] == 'cancelled':
            raise ValueError('Запись отменена')
        cursor.execute("UPDATE operator_audio_assets SET status='processing' WHERE id=%s AND status IN ('queued','failed')", (asset['id'],))
        provider = SpeechKit()
        if asset['kind']=='transcription':
            operation = asset.get('provider_operation_id')
            if not operation:
                if (asset.get('metadata_json') or {}).get('provider_starting'):
                    raise ValueError('Предыдущая отправка в сервис речи не подтверждена. Запишите новое сообщение')
                path = private_path(asset['path'])
                normalized = audio_root() / (asset['id']+'.ogg')
                duration = normalize_audio(path,normalized)
                cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"provider_starting\":true}'::jsonb WHERE id=%s",(asset['id'],))
                db.conn.commit()
                operation = provider.start(normalized.read_bytes())
                cursor.execute('UPDATE operator_audio_assets SET provider_operation_id=%s,duration=%s WHERE id=%s',(operation,duration,asset['id']))
                db.conn.commit()
            text = None
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                cursor.execute('SELECT status,lease_token FROM operator_async_jobs WHERE id=%s',(claimed['id'],))
                job = _row(cursor,cursor.fetchone())
                if job.get('status')!='running' or job.get('lease_token')!=claimed.get('lease_token'):
                    raise ValueError('Обработка записи отменена')
                text = provider.result(operation)
                if text is not None:
                    break
                time.sleep(2)
            if text is None:
                raise ValueError('Распознавание ещё не завершено. Повторите проверку')
            if not text:
                raise ValueError('Не удалось расслышать речь. Запишите сообщение ещё раз')
            authorize_actor(cursor,asset['user_id'],asset['business_id'])
            cursor.execute("UPDATE operator_audio_assets SET transcript=%s,status='ready',path=NULL WHERE id=%s",(text,asset['id']))
            if asset.get('path'):
                private_path(asset['path']).unlink(missing_ok=True)
            result=finance_transcription_result(cursor,asset,text)
        else:
            cursor.execute('SELECT content FROM operatormessages WHERE id=%s AND user_id=%s',(asset['message_id'],asset['user_id']))
            text = str(_row(cursor,cursor.fetchone()).get('content') or '')[:1000]
            if not text:
                raise ValueError('Нет текста для озвучивания')
            if (asset.get('metadata_json') or {}).get('provider_starting'):
                raise ValueError('Предыдущее озвучивание не подтверждено. Текст ответа сохранён')
            cursor.execute("UPDATE operator_audio_assets SET metadata_json=metadata_json || '{\"provider_starting\":true}'::jsonb WHERE id=%s",(asset['id'],))
            db.conn.commit()
            content = provider.synthesize(text)
            path = audio_root()/(asset['id']+'.ogg')
            path.write_bytes(content)
            path.chmod(0o600)
            mime = 'audio/ogg'
            if asset['channel'] != 'telegram':
                mp3 = audio_root()/(asset['id']+'.mp3')
                subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(path),'-y',str(mp3)],capture_output=True,check=True,timeout=30)
                path.unlink(missing_ok=True)
                path = mp3
                path.chmod(0o600)
                mime = 'audio/mpeg'
            authorize_actor(cursor,asset['user_id'],asset['business_id'])
            cursor.execute("UPDATE operator_audio_assets SET status='ready',path=%s,format=%s WHERE id=%s",(str(path),mime,asset['id']))
            result={'asset_id':asset['id'],'audio_url':'/api/operator/audio/'+asset['id'],'message_id':asset['message_id']}
        cursor.execute('SELECT status,lease_token FROM operator_async_jobs WHERE id=%s FOR UPDATE',(claimed['id'],))
        current = _row(cursor,cursor.fetchone())
        if current.get('status') != 'running' or current.get('lease_token') != claimed.get('lease_token'):
            db.conn.rollback()
            raise ValueError('Обработка отменена или передана другому исполнителю')
        db.conn.commit()
        logging.getLogger(__name__).info('operator_audio_completed kind=%s elapsed_ms=%s',asset['kind'],round((time.monotonic()-started_at)*1000))
        return result
    finally:
        if normalized:
            normalized.unlink(missing_ok=True)
        db.close()
