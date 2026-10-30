"""MAX attachments reuse private Operator files and durable audio jobs."""
import json
from urllib.parse import urlsplit

from services.max_tls import max_ssl_context
from core.outbound_network import public_pinned_get
from services.operator_conversations import _row


def download_input(url):
    if not isinstance(url, str) or urlsplit(url).scheme != 'https':
        raise ValueError('Некорректная ссылка на вложение MAX')
    try:
        fetched = public_pinned_get(url, {}, timeout=20, max_bytes=10*1024*1024+1, ssl_context=max_ssl_context())
    except Exception:
        raise ValueError('Не удалось скачать вложение MAX') from None
    if fetched.status_code != 200 or not fetched.body or len(fetched.body) > 10*1024*1024:
        raise ValueError('Файл недоступен или больше 10 МБ')
    return fetched.body, fetched.headers.get('content-type', '').split(';')[0]


def is_audio_attachment(attachment):
    from services.operator_audio import is_audio_document
    details = attachment.get('payload') or {}
    return attachment.get('type') == 'audio' or attachment.get('type') == 'file' and is_audio_document(
        attachment.get('filename') or details.get('filename'), attachment.get('mime_type') or details.get('mime_type'))


def receive_inputs(cursor, attachments, *, user_id, business_id, max_id, event_key, caption=""):
    from services.operator_audio import create_transcription
    from services import operator_attachments, operator_photo_brief
    if not isinstance(attachments, list) or len(attachments) > 10:
        raise ValueError('В одном сообщении допускается до 10 вложений')
    for index, attachment in enumerate(attachments):
        if not isinstance(attachment, dict):
            raise ValueError('Некорректное вложение MAX')
        kind = attachment.get('type')
        if kind not in {'image', 'audio', 'file'}:
            raise ValueError('Пришлите фото, голосовую запись, PDF, XLSX или CSV')
        content, mime = download_input((attachment.get('payload') or {}).get('url'))
        key = f'max:{event_key}:{index}'
        if is_audio_attachment(attachment):
            if len(attachments) != 1:
                raise ValueError('Голосовое сообщение нужно отправить отдельно')
            create_transcription(cursor, content=content, user_id=user_id, business_id=business_id,
                channel='max_bot', conversation_id=None, request_id=key,
                metadata={'max_id': max_id, 'business_id': business_id,
                          'photo_brief_ids': operator_photo_brief.voice_snapshot(cursor, business_id, user_id, 'max_bot')})
            return 'Голосовое получено. Распознаю и обработаю команду; результат придёт сюда.'
        fallback = {'image/png': 'photo.png', 'image/webp': 'photo.webp',
                    'application/pdf': 'document.pdf', 'text/csv': 'table.csv',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'table.xlsx'}.get(mime, 'photo.jpg')
        name = str(attachment.get('filename') or (attachment.get('payload') or {}).get('filename') or fallback)
        item = operator_attachments.receive(cursor, business_id=business_id, user_id=user_id, channel='max_bot',
            content=content, name=name, mime_type=mime, request_key=key)
        if operator_photo_brief.register(cursor, item, caption=caption, group_key=event_key):
            continue
        cursor.execute('SELECT input_context_json FROM operatorconversations WHERE id=%s FOR UPDATE', (item['conversation_id'],))
        context = _row(cursor, cursor.fetchone()).get('input_context_json') or {}
        ids = list(dict.fromkeys((context.get('attachment_ids') or []) + [item['id']]))
        if len(ids) > 10:
            raise ValueError('Завершите текущий материал перед добавлением новых файлов')
        context['attachment_ids'] = ids
        cursor.execute('UPDATE operatorconversations SET input_context_json=%s::jsonb WHERE id=%s', (json.dumps(context), item['conversation_id']))
    return None


def enqueue_voice_result(cursor, asset):
    from psycopg2.extras import Json
    cursor.execute('SELECT transcript FROM operator_audio_assets WHERE id=%s', (asset['id'],))
    transcript = _row(cursor, cursor.fetchone()).get('transcript')
    if not transcript:
        return
    metadata = asset.get('metadata_json') or {}
    payload = {'update_type': 'localos_voice_ready', 'max_id': metadata.get('max_id'),
               'business_id': asset['business_id'], 'asset_id': asset['id'],
               'conversation_id': asset['conversation_id'], 'transcript': transcript}
    cursor.execute('''INSERT INTO max_webhook_events(event_key,payload_json) VALUES (%s,%s)
        ON CONFLICT(event_key) DO NOTHING''', ('voice:' + asset['id'], Json(payload)))
