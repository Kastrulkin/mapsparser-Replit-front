"""Shared, explicit currency/timezone settings for conversational input."""
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from services.operator_conversations import _row


def authorize_write(cursor, business_id, user_id):
    from services.operator_audio import authorize_actor
    actor, _ = authorize_actor(cursor, user_id, business_id)
    if actor.get('role') != 'business_owner' and not actor.get('is_superadmin'):
        raise PermissionError('Сохранить валюту и часовой пояс может владелец бизнеса.')


# Cities are explicit user input, never inferred from a business name or location.
CITY_ZONES = {
    'таллин': ('Таллин', 'Europe/Tallinn'), 'таллинн': ('Таллин', 'Europe/Tallinn'),
    'москва': ('Москва', 'Europe/Moscow'), 'москве': ('Москва', 'Europe/Moscow'),
    'лондон': ('Лондон', 'Europe/London'), 'пхукет': ('Пхукет', 'Asia/Bangkok'),
    'бангкок': ('Бангкок', 'Asia/Bangkok'), 'санкт-петербург': ('Санкт-Петербург', 'Europe/Moscow'),
    'петербург': ('Санкт-Петербург', 'Europe/Moscow'), 'рига': ('Рига', 'Europe/Riga'),
    'вильнюс': ('Вильнюс', 'Europe/Vilnius'), 'дубай': ('Дубай', 'Asia/Dubai'),
    'берлин': ('Берлин', 'Europe/Berlin'), 'париж': ('Париж', 'Europe/Paris'),
    'алматы': ('Алматы', 'Asia/Almaty'), 'тбилиси': ('Тбилиси', 'Asia/Tbilisi'),
    'ереван': ('Ереван', 'Asia/Yerevan'), 'минск': ('Минск', 'Europe/Minsk'),
    'екатеринбург': ('Екатеринбург', 'Asia/Yekaterinburg'), 'новосибирск': ('Новосибирск', 'Asia/Novosibirsk'),
}


def parse_settings(message):
    data = {}
    currency = re.search(r'\bвалюта\s*[:=-]?\s*([A-Z]{3})\b', message, re.I) or re.search(r'\b(EUR|USD|RUB|KZT|BYN|GBP|GEL|AMD|AED|UZS|KGS|TRY|THB)\b', message, re.I)
    if currency:
        data['currency'] = currency.group(1).upper()
    else:
        for name, code in [('евро', 'EUR'), ('рубл', 'RUB'), ('доллар', 'USD'), ('тенге', 'KZT'), ('бат', 'THB')]:
            if re.search(r'\b' + name, message, re.I):
                data['currency'] = code
                break
    zone = re.search(r'\b(?:Europe|Asia|America|Africa|Australia|Pacific|Atlantic|Indian)/[A-Za-z_/-]+\b|\bUTC\b', message, re.I)
    if zone:
        # Canonicalize case without guessing offsets or ambiguous cities.
        from zoneinfo import available_timezones
        data['timezone'] = next((z for z in available_timezones() if z.casefold() == zone.group().casefold()), zone.group())
    city = re.search(r'\bгород\s*[:—=-]?\s*([^;,.!?\n]+)', message, re.I)
    if city:
        value = re.split(r'\s+(?:и|валюта|часовой|используем)\b', city.group(1), maxsplit=1, flags=re.I)[0].strip()
        if value and len(value) <= 120:
            data['city'] = value
    for name, (label, timezone_name) in CITY_ZONES.items():
        if re.search(r'(?<!\w)' + re.escape(name) + r'(?:е|а)?(?!\w)', message, re.I):
            data['city'] = label
            if not zone:
                data['timezone'] = timezone_name
            break
    if 'city' in data and 'timezone' not in data:
        from zoneinfo import available_timezones
        matches = [z for z in available_timezones() if '/' in z and z.split('/')[-1].replace('_', ' ').casefold() == data['city'].casefold()]
        if len(matches) == 1:
            data['timezone'] = matches[0]
    return data


def required_settings(message):
    """Only intercept operations whose meaning depends on missing defaults."""
    relative = bool(re.search(r'сегодня|завтра|вчера|недел|месяц|следующ', message, re.I))
    read = bool(re.search(r'покажи|выдай|како|когда|есть ли|сколько|посмотр', message, re.I))
    money_write = not read and bool(re.search(r'выруч|продаж|чек|расход|возврат|доход|(?:добав|созда).*услуг', message, re.I))
    fields = []
    if money_write and not parse_settings(message).get('currency'):
        fields.append('currency')
    dated = money_write or bool(re.search(r'пост|контент|визит|клиент|финанс', message, re.I))
    if relative and dated:
        fields.append('timezone')
    return fields


def settings_summary(data):
    labels = {'city': 'город', 'currency': 'валюта', 'timezone': 'часовой пояс'}
    return ', '.join(labels[key] + ': ' + str(data[key]) for key in labels if data.get(key))


def route_setup(cursor, business_id, user_id, channel, message, pending, conversation_id, orchestrator):
    from services import operator_request_history, finance_daily
    explicit_setup = bool(re.search(r'(?:сохран|укаж|настро|установ|постав|измени|поменя).*?(?:валют|часов.*пояс|город)|настройки бизнеса\s*:|^\s*(?:город|валюта|часовой пояс)\s*[:—=-]?\s*\S', message, re.I))
    if re.match(r'\s*(?:если|например|допустим|как\b)', message, re.I):
        return None
    if re.search(r'\bпост(?:а|ы|ов|у|ом|е)?\b|контент|отзыв|новост', message, re.I) and not re.search(r'настройк', message, re.I):
        explicit_setup = False
    parsed = parse_settings(message)
    setup_pending = pending.get('capability') == 'settings.input'
    # A new task replaces an unfinished clarification. Place/currency mentions
    # inside a post or another task are not interpreted as settings answers.
    new_task = bool(re.search(r'\bпост(?:а|ы|ов|у|ом|е)?\b|контент|отзыв|время работы|выруч|продаж|покажи|выдай|когда|клиент|услуг', message, re.I))
    waiting = setup_pending and not new_task and bool(parsed)
    if setup_pending and message.strip().casefold() in {'отмена', 'отмени', '/cancel', 'стоп', 'не надо'}:
        return {'status': 'cancelled', 'capability': 'settings.input', 'chat_response': 'Настройка отменена. Можно задать другую команду.'}, {}
    if not explicit_setup and not waiting and (not operator_request_history.enabled(business_id) or (pending and not setup_pending)):
        return None
    required = list(pending.get('required_fields') or required_settings(pending.get('source_message') or '')) if waiting else required_settings(message)
    current = resolve(cursor, business_id)
    if not explicit_setup and not waiting and not any(not current.get(field) for field in required):
        return None
    try:
        authorize_write(cursor, business_id, user_id)
    except PermissionError:
        return {'status': 'clarification_required', 'capability': 'settings.input',
                'chat_response': 'Для этой команды не хватает настроек бизнеса. Владелец может указать город, часовой пояс или валюту в Операторе.'}, {}
    original = pending.get('source_message') if waiting else '' if explicit_setup else message
    from datetime import datetime, timezone
    received_at = pending.get('source_received_at') if waiting else None
    received_at = received_at or datetime.now(timezone.utc).isoformat()
    data = dict(pending.get('settings') or {}) if waiting else {}
    if waiting or explicit_setup:
        data.update(parsed)
    # A newly specified city must not silently retain the old city's timezone.
    unknown_city_zone = bool(data.get('city') and not data.get('timezone') and data.get('city') != current.get('city'))
    if unknown_city_zone and 'timezone' not in required:
        required.append('timezone')
    next_context = {'capability': 'settings.input', 'source_message': original, 'source_received_at': received_at,
                    'settings': data, 'required_fields': required}
    missing = [field for field in required if not data.get(field) and (not current.get(field) or (field == 'timezone' and unknown_city_zone))]
    if not data or missing:
        labels = {'currency': 'валюту', 'timezone': 'часовой пояс (можно назвать город)'}
        question = ' и '.join(labels[field] for field in missing) or 'город, валюту или часовой пояс'
        return {'status': 'clarification_required', 'capability': 'settings.input',
                'chat_response': 'Укажите ' + question + '. Например: «Таллин» или «валюта евро». Можно задать другую команду или отменить настройку.'}, next_context
    try:
        envelope = finance_daily.prepare(cursor, business_id, user_id, {'kind': 'settings', **data}, channel, conversation_id)
    except (ValueError, ZoneInfoNotFoundError):
        import sys
        return {'status': 'clarification_required', 'capability': 'settings.input', 'chat_response': str(sys.exception())}, next_context
    from services.operator_core import _prepare_registered_capability_approval
    preview = 'Сохранить настройки бизнеса: ' + settings_summary(envelope['data']) + '?'
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
    for field in ('currency', 'timezone', 'city'):
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


def validate_patch(args, current):
    """Validate only supplied settings; other defaults may remain unknown."""
    data = {key: str(args[key]).strip() for key in ('currency', 'timezone', 'city') if args.get(key) is not None}
    if not data:
        raise ValueError('Укажите город, валюту или часовой пояс.')
    if 'currency' in data:
        data['currency'] = data['currency'].upper()
        if not re.fullmatch('[A-Z]{3}', data['currency']):
            raise ValueError('Уточните валюту трёхбуквенным кодом, например EUR или RUB.')
    if 'timezone' in data:
        try:
            ZoneInfo(data['timezone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Уточните часовой пояс, например Europe/Tallinn или Asia/Bangkok.')
    if 'city' in data:
        if not data['city'] or len(data['city']) > 120 or any(char in data['city'] for char in '\n;'):
            raise ValueError('Укажите название города, до 120 символов.')
        if data['city'] != current.get('city') and not data.get('timezone'):
            raise ValueError('Уточните часовой пояс для нового города. Он будет показан перед сохранением.')
    return data
