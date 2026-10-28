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



def work_selection(cursor, *, item_type='content_item', **kwargs):
    if item_type == 'content_item':
        return content_selection(cursor, **kwargs)
    if item_type == 'finance_input':
        from services import finance_daily
        finance_daily.authorize(cursor, kwargs['business_id'], kwargs['user_id'], write=True)
        if str(kwargs['item_id']) != str(kwargs['business_id']):
            raise PermissionError('Выберите показатели текущего бизнеса.')
        return {'item_id': str(kwargs['business_id']), 'version': 'finance-input-v1', 'kind': 'finance_input'}
    if item_type == 'day_brief':
        from services import operator_day_brief
        operator_day_brief.authorize(cursor, kwargs['business_id'], kwargs['user_id'], owner=True)
        if not str(kwargs.get('item_id') or '').strip():
            raise ValueError('Сначала сохраните черновик планёрки, затем продолжите в боте.')
        value = operator_day_brief.draft(cursor, kwargs['business_id'], kwargs['user_id'], identifier=kwargs['item_id'])
        if not value:
            raise PermissionError('Планёрка недоступна.')
        return {'item_id': value['id'], 'version': str(value['version'])}
    if item_type == 'partner':
        from services.operator_partner_work import partner_selection
        return partner_selection(cursor, **kwargs)
    raise ValueError('Этот тип обсуждения не поддерживается.')


def mobile_work_url(business_id, item_id=None, platform='telegram', screen='content', item_type='content_item'):
    if platform not in {'telegram', 'max'}:
        raise ValueError('Неизвестная платформа.')
    params = {'screen': screen, 'scope_type': 'business', 'scope_id': str(business_id)}
    if item_id:
        params.update(item_type=item_type, item_id=str(item_id))
    elif screen == 'work_journal' and item_type == 'day_brief':
        params['item_type'] = 'day_brief'  # Open the briefing tab even before the first draft exists.
    return 'https://localos.pro/' + platform + '/control?' + urlencode(params)


def prepare_handoff(cursor, *, user_id, business_id, platform, item_id, request_id, updated_at=None, item_type='content_item'):
    if platform not in {'telegram', 'max'}:
        raise ValueError('Неизвестная платформа.')
    uuid.UUID(str(request_id))
    selection = work_selection(cursor, item_type=item_type, user_id=user_id, business_id=business_id, item_id=item_id, expected_updated_at=updated_at)
    selected_key = {'partner': 'selected_partner', 'day_brief': 'selected_day_brief', 'finance_input': 'selected_finance'}.get(item_type, 'selected_item')
    screen = {'partner': 'partnerships', 'day_brief': 'work_journal', 'finance_input': 'finance_import'}.get(item_type, 'content')
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
    other_key = 'selected_item' if item_type == 'partner' else 'selected_partner'
    if any(current.get(key) for key in ('selected_item', 'selected_partner', 'selected_day_brief', 'selected_finance') if key != selected_key):
        raise ValueError('Этот переход уже используется для другого обсуждения.')
    if current.get(selected_key) and current[selected_key]['item_id'] != selection['item_id']:
        raise ValueError('Этот переход уже создан для другого партнёра.' if item_type == 'partner' else 'Этот переход уже создан для другого поста.')
    if current.get(selected_key) and current[selected_key].get('version') != selection['version']:
        raise ValueError('Карточка партнёра изменилась. Откройте её заново перед переходом.' if item_type == 'partner' else 'Пост изменился. Откройте его заново перед переходом.')
    stored = conversation.get('input_context_json') or {}
    if isinstance(stored, str):
        stored = json.loads(stored)
    if stored.get('work_handoff') and stored['work_handoff'] != selection:
        raise ValueError('Этот переход устарел. Откройте актуальную карточку партнёра заново.' if item_type == 'partner' else 'Этот переход устарел. Откройте актуальный пост заново.')
    pending = {'capability': {'partner': 'partnerships.selected', 'day_brief': 'work.day_brief', 'finance_input': 'finance.daily.input'}.get(item_type, 'content.editorial.selected'), selected_key: selection}
    # A repeated link request must not reset a financial preview or clarification.
    if item_type != 'finance_input' or not stored.get('work_handoff'):
        set_operator_pending_context(cursor, str(conversation['id']), pending)
    if not stored.get('work_handoff'):
        # Preparing a link cannot steal the bot's currently active discussion.
        cursor.execute("UPDATE operatorconversations SET status='handoff_prepared',input_context_json=%s::jsonb WHERE id=%s AND user_id=%s",
            (json.dumps({'work_handoff': selection}), str(conversation['id']), user_id))
    return {'url': base + name + '?start=work_' + uuid.UUID(str(conversation['id'])).hex,
            'return_url': mobile_work_url(business_id, None if item_type == 'finance_input' else item_id, platform, screen, item_type), selected_key: selection}


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
    stored = conversation.get('input_context_json') or {}
    if isinstance(stored, str):
        stored = json.loads(stored)
    finance_selection = (stored.get('work_handoff') or {}) if (stored.get('work_handoff') or {}).get('kind') == 'finance_input' else pending.get('selected_finance')
    item_type = 'finance_input' if finance_selection else 'day_brief' if pending.get('selected_day_brief') else 'partner' if pending.get('selected_partner') else 'content_item'
    selected = finance_selection or pending.get('selected_day_brief') or pending.get('selected_partner') or pending.get('selected_item') or {}
    selection = work_selection(cursor, item_type=item_type, user_id=user_id, business_id=str(conversation['business_id']), item_id=selected.get('item_id'))
    # Reopening an old link must not silently approve a stale content version.
    if selected.get('version') != selection['version']:
        raise ValueError('Карточка партнёра изменилась. Откройте её в мини-приложении и начните обсуждение заново.' if item_type == 'partner' else 'Пост изменился. Откройте его в мини-приложении и начните обсуждение заново.')
    cursor.execute("UPDATE operatorconversations SET status='active',updated_at=NOW() WHERE id=%s AND user_id=%s", (identifier, user_id))
    return {'business_id': str(conversation['business_id']), 'conversation_id': identifier,
            'item_type': item_type, 'return_url': mobile_work_url(conversation['business_id'], None if item_type == 'finance_input' else selection['item_id'], platform,
                {'partner': 'partnerships', 'day_brief': 'work_journal', 'finance_input': 'finance_import'}.get(item_type, 'content'), item_type)}


def read_selected_content(cursor, *, business_id, user_id, message, selection):
    """Read the explicitly selected saved post without asking a model to find it."""
    import re
    if not isinstance(selection, dict) or not selection.get('item_id'):
        return None
    if not re.fullmatch(r'\s*(?:пожалуйста[,\s]*)?(?:покажи|покажите|прочитай|прочитайте)\s+(?:мне\s+)?(?:полный\s+)?(?:текст\s+(?:этого|выбранного)\s+поста|(?:этот|выбранный)\s+пост)(?:\s+целиком)?[.!?]?\s*', str(message), re.I):
        return None
    current = content_selection(cursor, user_id=user_id, business_id=business_id, item_id=selection['item_id'])
    from services import operator_editorial
    row = operator_editorial._items(cursor, business_id, item_id=current['item_id'])[0]
    text = str(row.get('draft_text') or '').strip()
    return {'status': 'completed', 'chat_response': text or 'У выбранного поста пока нет текста. Откройте пост и подготовьте черновик.',
            'selected_item': current, 'external_writes_performed': False,
            'result_ref': {'href': '/dashboard/content', 'label': 'Открыть контент', 'entity_type': 'content'}}
