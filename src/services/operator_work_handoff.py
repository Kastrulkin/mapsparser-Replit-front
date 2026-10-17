"""Authorized work selection shared by messenger bots and mobile workspaces.

Opening a handoff never invokes the Operator or confirms a business action.
The existing conversation storage owns the selection; no second task store.
"""
import json
import os
import uuid
from datetime import datetime
from urllib.parse import urlencode

from services.operator_conversations import _row, get_or_create_operator_conversation, set_operator_pending_context


def content_selection(cursor, *, user_id, business_id, item_id, expected_updated_at=None):
    from services.operator_audio import authorize_actor
    from services import operator_editorial
    _, access = authorize_actor(cursor, user_id, business_id, require_write=True)
    from subscription_manager import capability_access_payload
    if not capability_access_payload(access, 'social_content').get('allowed'):
        raise PermissionError('Контент недоступен на текущем тарифе этого бизнеса. Проверьте доступ в настройках.')
    uuid.UUID(str(item_id))
    rows = operator_editorial._items(cursor, business_id, item_id=str(item_id))
    if len(rows) != 1 or str(rows[0]['id']) != str(item_id):
        raise PermissionError('Пост недоступен в выбранном бизнесе.')
    row = rows[0]
    if expected_updated_at:
        seen = datetime.fromisoformat(str(expected_updated_at).replace('Z', '+00:00'))
        current = datetime.fromisoformat(str(row.get('updated_at')).replace('Z', '+00:00'))
        if seen != current:
            raise ValueError('Пост изменился. Обновите список и проверьте актуальный текст.')
    if row.get('plan_status') == 'archived':
        raise ValueError('План архивирован. Выберите пост из действующего плана.')
    return {'item_id': str(row['id']), 'plan_id': str(row['plan_id']), 'version': operator_editorial._version(row)}


def mobile_work_url(business_id, item_id=None, platform='telegram', screen='content'):
    if platform not in {'telegram', 'max'}:
        raise ValueError('Неизвестная платформа.')
    params = {'screen': screen, 'scope_type': 'business', 'scope_id': str(business_id)}
    if item_id:
        params.update(item_type='content_item', item_id=str(item_id))
    return 'https://localos.pro/' + platform + '/control?' + urlencode(params)


def prepare_handoff(cursor, *, user_id, business_id, platform, item_id, request_id, updated_at=None):
    if platform not in {'telegram', 'max'}:
        raise ValueError('Неизвестная платформа.')
    uuid.UUID(str(request_id))
    selection = content_selection(cursor, user_id=user_id, business_id=business_id, item_id=item_id, expected_updated_at=updated_at)
    if platform == 'telegram':
        cursor.execute('SELECT telegram_id FROM users WHERE id=%s AND is_active=TRUE', (user_id,))
        binding = _row(cursor, cursor.fetchone()).get('telegram_id')
        name = os.getenv('TELEGRAM_BOT_USERNAME', 'LocalOspro_bot').strip().removeprefix('@')
        base = 'https://t.me/'
    else:
        cursor.execute('SELECT max_id FROM max_identities WHERE user_id=%s AND revoked_at IS NULL', (user_id,))
        binding = _row(cursor, cursor.fetchone()).get('max_id')
        name = os.getenv('MAX_BOT_USERNAME', '').strip().removeprefix('@')
        base = 'https://max.ru/'
    if not binding or not name or not name.replace('_', '').isalnum():
        raise ValueError('Сначала подключите аккаунт и бота этого мессенджера в настройках.')
    channel = 'max_bot' if platform == 'max' else 'telegram'
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('work-handoff:' + user_id + ':' + request_id,))
    conversation = get_or_create_operator_conversation(cursor, business_id=business_id, user_id=user_id,
        channel=channel, transport_key='work-handoff:' + request_id)
    current = conversation.get('pending_context') or {}
    if isinstance(current, str):
        current = json.loads(current)
    if current.get('selected_item') and current['selected_item']['item_id'] != selection['item_id']:
        raise ValueError('Этот переход уже создан для другого поста.')
    if current.get('selected_item') and current['selected_item'].get('version') != selection['version']:
        raise ValueError('Пост изменился. Откройте его заново перед переходом.')
    stored = conversation.get('input_context_json') or {}
    if isinstance(stored, str):
        stored = json.loads(stored)
    if stored.get('work_handoff') and stored['work_handoff'] != selection:
        raise ValueError('Этот переход устарел. Откройте актуальный пост заново.')
    pending = {'capability': 'content.editorial.selected', 'selected_item': selection}
    set_operator_pending_context(cursor, str(conversation['id']), pending)
    if not stored.get('work_handoff'):
        # Preparing a link cannot steal the bot's currently active discussion.
        cursor.execute("UPDATE operatorconversations SET status='handoff_prepared',input_context_json=%s::jsonb WHERE id=%s AND user_id=%s",
            (json.dumps({'work_handoff': selection}), str(conversation['id']), user_id))
    return {'url': base + name + '?start=work_' + uuid.UUID(str(conversation['id'])).hex,
            'return_url': mobile_work_url(business_id, item_id, platform), 'selected_item': selection}


def resume_handoff(cursor, *, user_id, token, platform):
    channel = {'telegram': 'telegram', 'max': 'max_bot'}.get(platform)
    if not channel:
        raise ValueError('Неизвестная платформа.')
    identifier = str(uuid.UUID(token.removeprefix('work_')))
    cursor.execute("SELECT * FROM operatorconversations WHERE id=%s AND user_id=%s AND channel=%s AND status IN ('active','handoff_prepared')",
                   (identifier, user_id, channel))
    conversation = _row(cursor, cursor.fetchone())
    if not conversation:
        raise PermissionError('Переход недоступен. Откройте пост в своём кабинете.')
    pending = conversation.get('pending_context') or {}
    if isinstance(pending, str):
        pending = json.loads(pending)
    selected = pending.get('selected_item') or {}
    selection = content_selection(cursor, user_id=user_id, business_id=str(conversation['business_id']), item_id=selected.get('item_id'))
    # Reopening an old link must not silently approve a stale content version.
    if selected.get('version') != selection['version']:
        raise ValueError('Пост изменился. Откройте его в мини-приложении и начните обсуждение заново.')
    cursor.execute("UPDATE operatorconversations SET status='active',updated_at=NOW() WHERE id=%s AND user_id=%s", (identifier, user_id))
    return {'business_id': str(conversation['business_id']), 'conversation_id': identifier,
            'return_url': mobile_work_url(conversation['business_id'], selection['item_id'], platform)}
