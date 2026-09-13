"""Shared, explicit currency/timezone settings for conversational input."""
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from services.operator_conversations import _row


def authorize_write(cursor, business_id, user_id):
    from services.operator_audio import authorize_actor
    actor, _ = authorize_actor(cursor, user_id, business_id)
    if actor.get('role') != 'business_owner' and not actor.get('is_superadmin'):
        raise PermissionError('Сохранить валюту и часовой пояс может владелец бизнеса.')


def route_setup(cursor, business_id, user_id, channel, message, pending, conversation_id, orchestrator):
    """Ask once on first date/money-dependent input; never infer a tenant default."""
    from services import operator_request_history, finance_daily
    correcting = bool(re.match(r'нет\b|исправ|вернее|точнее|отмен|стоп|/cancel|[A-Z]{3}\b|Europe/|Asia/|America/', message, re.I))
    waiting = pending.get('capability') == 'settings.input' and (pending.get('stage') != 'approval' or correcting)
    explicit_setup = bool(re.search(r'(?:сохрани|укажи|настрой).*?(?:валют|часов.*пояс)', message, re.I))
    if not operator_request_history.enabled(business_id) and not waiting and not explicit_setup:
        return None
    if not waiting and pending:
        return None
    if not waiting and not explicit_setup and not re.search(r'сегодня|завтра|вчера|недел|месяц|следующ.*(?:пост|клиент|визит)|выруч|продаж|добав.*услуг', message, re.I):
        return None
    current = resolve(cursor, business_id)
    if not waiting and not explicit_setup and current.get('currency') and current.get('timezone'):
        return None
    if waiting and message.strip().casefold() in {'отмена', 'отмени', '/cancel', 'стоп', 'не надо'}:
        return {'status': 'cancelled', 'capability': 'settings.input', 'chat_response': 'Настройка и исходная команда отменены.'}, {}
    try:
        authorize_write(cursor, business_id, user_id)
    except PermissionError:
        return {'status': 'clarification_required', 'capability': 'settings.input',
                'chat_response': 'Для этой команды нужны валюта и часовой пояс бизнеса. Попросите владельца указать их в Операторе.'}, {}
    original = pending.get('source_message') if waiting else '' if explicit_setup else message
    from datetime import datetime, timezone
    received_at = pending.get('source_received_at') or datetime.now(timezone.utc).isoformat()
    data = dict(pending.get('settings') or {})
    currency = re.search(r'\b(EUR|USD|RUB|KZT|BYN|GBP|GEL|AMD|AED|UZS|KGS|TRY)\b', message, re.I)
    if currency:
        data['currency'] = currency.group(1).upper()
    else:
        for name, code in [('евро', 'EUR'), ('рубл', 'RUB'), ('доллар', 'USD'), ('тенге', 'KZT')]:
            if name in message.casefold():
                data['currency'] = code
                break
    zone = re.search(r'\b(?:Europe|Asia|America|Africa|Australia|Pacific|Atlantic|Indian)/[A-Za-z_/-]+\b|\bUTC\b', message)
    if zone:
        data['timezone'] = zone.group(0)
    for city, name in [('таллин', 'Europe/Tallinn'), ('москв', 'Europe/Moscow'), ('лондон', 'Europe/London')]:
        if city in message.casefold() and not zone:
            data['timezone'] = name
    for field in ('currency', 'timezone'):
        if not data.get(field) and current.get(field):
            data[field] = current[field]
    next_context = {'capability': 'settings.input', 'source_message': original, 'source_received_at': received_at, 'settings': data}
    try:
        if not data.get('currency') or not data.get('timezone'):
            raise ValueError('missing')
        envelope = finance_daily.prepare(cursor, business_id, user_id, {'kind': 'settings', **data}, channel, conversation_id)
    except (ValueError, ZoneInfoNotFoundError):
        return {'status': 'clarification_required', 'capability': 'settings.input',
                'chat_response': 'Какую валюту и часовой пояс использовать для бизнеса? Например: «EUR, Europe/Tallinn». Покажу настройки на подтверждение, затем продолжу исходную команду.'}, next_context
    from services.operator_core import _prepare_registered_capability_approval
    preview = 'Сохранить для бизнеса валюту ' + data['currency'] + ' и часовой пояс ' + data['timezone'] + '?'
    result = _prepare_registered_capability_approval(capability='settings.input', tool_name='settings.input',
        business_id=business_id, user_id=user_id, channel=channel, message=preview + '\n' + finance_daily.fingerprint(envelope),
        payload=envelope, backend_capability='finance.daily.apply_operator', orchestrator=orchestrator)
    if result.get('status') == 'approval_required':
        next_context['stage'] = 'approval'
        result['chat_response'] = preview + ('\nЗатем продолжу: «' + original + '».' if original else '')
        result['approval']['summary'] = result['chat_response']
        result['approval']['envelope'].update(resume_message=original, resume_channel=channel, resume_conversation_id=conversation_id, resume_received_at=received_at)
    return result, next_context


def resolve(cursor, business_id):
    cursor.execute('SELECT to_jsonb(b) data FROM businesses b WHERE id=%s', (business_id,))
    business = _row(cursor, cursor.fetchone()).get('data') or {}
    cursor.execute("SELECT to_regclass('business_finance_settings') settings_table")
    configured = {}
    if _row(cursor, cursor.fetchone()).get('settings_table'):
        cursor.execute('SELECT * FROM business_finance_settings WHERE business_id=%s', (business_id,))
        configured = _row(cursor, cursor.fetchone())
    result = {'business_id': business_id, 'version': configured.get('version', 0), 'conflicts': [], 'candidates': {}}
    for field in ('currency', 'timezone'):
        explicit = configured.get(field)
        legacy = business.get(field)
        result['candidates'][field] = {'saved': explicit, 'legacy': legacy}
        if explicit and legacy and explicit != legacy:
            result['conflicts'].append(field)
        value = explicit or legacy
        if field == 'currency' and (not isinstance(value, str) or not re.fullmatch('[A-Z]{3}', value)):
            value = None
        if field == 'timezone' and value:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError, TypeError):
                value = None
        # A disagreement is surfaced for confirmation, never silently resolved.
        result[field] = None if field in result['conflicts'] else value
    return result
