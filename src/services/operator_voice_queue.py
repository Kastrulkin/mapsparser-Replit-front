"""Durable Telegram receipt and execution; neither operation sends chat messages."""
import json
import os
import requests
from database_manager import DatabaseManager
from services.operator_conversations import _row
from services.operator_audio import authorize_actor, create_transcription, load_asset, MAX_BYTES
from services.operator_async_jobs import create_operator_async_job
from core.telegram_network import build_requests_proxy_kwargs


def enqueue_execution(cursor, asset):
    metadata = asset.get('metadata_json') or {}
    if asset['channel'] != 'telegram' or not metadata.get('durable_execution'):
        return
    return create_operator_async_job(cursor, user_id=asset['user_id'], business_id=asset['business_id'],
        action_id=None, kind='voice_execute', payload={'asset_id': asset['id']},
        idempotency_key='voice-execute:'+asset['id'], stage='Обрабатываю команду')


def download(file_id):
    # Never propagate request exceptions: their URL contains the bot credential.
    token = os.environ['TELEGRAM_BOT_TOKEN']
    try:
        response = requests.post('https://api.telegram.org/bot'+token+'/getFile',
            json={'file_id': file_id}, timeout=(10, 30), **build_requests_proxy_kwargs())
        response.raise_for_status()
        data = response.json()
        if not data.get('ok'):
            raise ValueError('file unavailable')
        path = data['result']['file_path']
        if not isinstance(path, str) or '..' in path or '://' in path:
            raise ValueError('invalid file path')
        response = requests.get('https://api.telegram.org/file/bot'+token+'/'+path,
            stream=True, timeout=(10, 30), **build_requests_proxy_kwargs())
        response.raise_for_status()
        content = bytearray()
        try:
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ValueError('audio too large')
        finally:
            response.close()
        return bytes(content)
    except Exception:
        raise ValueError('Не удалось получить запись из Telegram. Задание сохранено для повторной попытки.') from None


def process_job(job):
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        authorize_actor(cursor, job['user_id'], job['business_id'])
        payload = job['payload_json']
        if job['kind'] == 'voice_receive':
            content = download(payload['file_id'])
            cursor.execute("SELECT status,lease_token,payload_json FROM operator_async_jobs WHERE id=%s FOR UPDATE",(job['id'],))
            state=_row(cursor,cursor.fetchone())
            if state.get('status')!='running' or state.get('lease_token')!=job.get('lease_token'):
                raise ValueError('Приём записи отменён')
            payload=state.get('payload_json') or payload
            result = create_transcription(cursor, content=content, user_id=job['user_id'],
                business_id=job['business_id'], channel='telegram', conversation_id=None,
                request_id=job['idempotency_key'], metadata=payload['metadata'])
            db.conn.commit()
            return result
        asset = load_asset(cursor, payload['asset_id'], job['user_id'], job['business_id'])
        metadata = asset.get('metadata_json') or {}
        if metadata.get('operator_payload'):
            return metadata['operator_payload']
        from services.telegram_control_scope import resolve_control_scope
        scope = resolve_control_scope(cursor,user_id=job['user_id']) or {}
        cursor.execute('SELECT telegram_id FROM users WHERE id=%s',(job['user_id'],))
        binding = _row(cursor,cursor.fetchone())
        if str(binding.get('telegram_id')) != str(metadata['chat_id']) or scope.get('kind') != 'business' or scope.get('id') != job['business_id']:
            result = {'text': 'Выбранный бизнес изменился. Команда отменена до выполнения.', 'result': {'status': 'cancelled'}}
        else:
            db.conn.commit()
            from services.telegram_dashboard import build_operator_chat_payload
            from services.operator_audio import VOICE_EXECUTION_CONTEXT
            execution_token=VOICE_EXECUTION_CONTEXT.set({'user_id':job['user_id'],'business_id':job['business_id'],'telegram_id':metadata['chat_id']})
            try:
                result = build_operator_chat_payload({'user_id': job['user_id'], 'business_id': job['business_id'],
                    'business_name': metadata.get('business_name'), 'telegram_id': str(metadata['chat_id']),
                    'operator_payload': {'conversation_id': asset['conversation_id'], 'transcription_id': asset['id'],
                                         'request_id': 'voice:'+asset['id']}}, asset['transcript'])
            finally:
                VOICE_EXECUTION_CONTEXT.reset(execution_token)
        cursor.execute('UPDATE operator_audio_assets SET metadata_json=metadata_json || %s::jsonb WHERE id=%s',
            (json.dumps({'operator_payload': result, 'execution_status': result['result'].get('status', 'completed')}), asset['id']))
        db.conn.commit()
        return result
    finally:
        db.close()
