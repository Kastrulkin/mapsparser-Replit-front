"""Reviewed period totals in the existing finance event journal, never spread over days."""
import calendar
import re
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from services import finance_daily
from services.operator_conversations import _row

MONTHS = ('январ', 'феврал', 'март', 'апрел', 'ма', 'июн', 'июл', 'август', 'сентябр', 'октябр', 'ноябр', 'декабр')


def dates(message, timezone_name=None):
    text = str(message).casefold().replace('ё', 'е')
    iso = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text)
    dotted = re.findall(r'\b\d{1,2}\.\d{1,2}\.\d{4}\b', text)
    if iso and dotted:
        raise ValueError('Укажите один период: дату начала и дату окончания.')
    if iso or dotted:
        values = iso or [datetime.strptime(v, '%d.%m.%Y').date().isoformat() for v in dotted]
        if len(values) != 2:
            raise ValueError('Укажите обе даты периода, например с 2026-10-19 по 2026-10-25.')
        start, end = map(date.fromisoformat, values)
    else:
        span = re.search(r'с\s+(\d{1,2})\s+по\s+(\d{1,2})\s+([а-я]+)\s+(\d{4})\b', text)
        named = re.search(r'за\s+([а-я]+)\s+(\d{4})\b', text)
        match = span or named
        if match:
            month_name = match[3] if span else match[1]
            month = next((i + 1 for i, name in enumerate(MONTHS) if re.fullmatch(name + (r'[йяе]' if i == 4 else r'[а-я]{0,2}'), month_name)), None)
            if not month:
                raise ValueError('Уточните месяц периода.')
            year = int(match[4] if span else match[2])
            start = date(year, month, int(match[1]) if span else 1)
            end = date(year, month, int(match[2]) if span else calendar.monthrange(year, month)[1])
        else:
            if not timezone_name:
                raise ValueError('Укажите точные даты начала и окончания периода или настройте часовой пояс бизнеса.')
            today = datetime.now(ZoneInfo(timezone_name)).date()
            if re.search(r'прошл\w*\s+недел', text):
                end = today - timedelta(days=today.weekday() + 1)
                start = end - timedelta(days=6)
            elif re.search(r'последн\w*\s+(?:7|семь)\s+дн', text):
                start, end = today - timedelta(days=6), today
            elif re.search(r'прошл\w*\s+месяц', text):
                end = today.replace(day=1) - timedelta(days=1)
                start = end.replace(day=1)
            elif re.search(r'(?:этот|текущ\w*)\s+месяц', text):
                start, end = today.replace(day=1), today
            else:
                raise ValueError('Уточните срок: точные даты, «за прошлую неделю» или «за сентябрь 2026».')
    if end <= start or (end - start).days > 366:
        raise ValueError('Укажите период от двух дней до одного года, с началом раньше окончания.')
    return start.isoformat(), end.isoformat()


def identifier(business_id, start, end, currency):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, ':'.join(('finance-period', business_id, start, end, currency))))


def current(cursor, business_id, target_id):
    cursor.execute("SELECT after_json FROM finance_daily_events WHERE business_id=%s AND target_id=%s AND kind='period' ORDER BY created_at DESC,(after_json->>'version')::int DESC,id DESC LIMIT 1", (business_id, target_id))
    return _row(cursor, cursor.fetchone()).get('after_json') or {}


def prepare(cursor, business_id, user_id, args, channel, message_ref):
    finance_daily.authorize(cursor, business_id, user_id, True)
    start, end = date.fromisoformat(args['period_start']).isoformat(), date.fromisoformat(args['period_end']).isoformat()
    if date.fromisoformat(end) <= date.fromisoformat(start) or (date.fromisoformat(end) - date.fromisoformat(start)).days > 366:
        raise ValueError('Укажите период от двух дней до одного года.')
    currency = str(args.get('currency') or finance_daily.settings(cursor, business_id).get('currency') or '').upper()
    if not re.fullmatch('[A-Z]{3}', currency):
        raise ValueError('Укажите валюту показателей, например рубли или евро.')
    values = finance_daily.checked_values(args.get('values'))
    if not any(values.get(key) is not None for key in finance_daily.FIELDS):
        raise ValueError('Укажите хотя бы один показатель: выручку, возвраты, расходы или количество чеков.')
    target = identifier(business_id, start, end, currency)
    before = current(cursor, business_id, target)
    return {'kind': 'period', 'mode': 'set', 'period_start': start, 'period_end': end, 'currency': currency,
            'data': values, 'before_version': before.get('version', 0), 'before_fingerprint': finance_daily.fingerprint(before),
            'target_id': target, 'channel': channel, 'message_ref': message_ref}


def apply(cursor, business_id, envelope):
    start, end, currency = envelope['period_start'], envelope['period_end'], envelope['currency']
    date.fromisoformat(start); date.fromisoformat(end)
    if start >= end or (date.fromisoformat(end) - date.fromisoformat(start)).days > 366 or not re.fullmatch('[A-Z]{3}', currency):
        raise ValueError('Некорректный период или валюта.')
    target = identifier(business_id, start, end, currency)
    if envelope.get('target_id') != target:
        raise ValueError('Назначение итога изменилось. Подготовьте новый просмотр.')
    before = current(cursor, business_id, target)
    if before.get('version', 0) != envelope['before_version'] or finance_daily.fingerprint(before) != envelope['before_fingerprint']:
        raise ValueError('Итог за этот период изменился. Проверьте актуальные показатели заново.')
    data = finance_daily.checked_values(envelope['data'])
    after = {'id': target, 'business_id': business_id, 'period_start': start, 'period_end': end, 'currency': currency,
             'values_json': data, 'version': before.get('version', 0) + 1, 'is_voided': False}
    return before, after


def preview(envelope):
    labels = {'revenue': 'Выручка до возвратов', 'refunds': 'Возвраты', 'expenses': 'Расходы', 'checks': 'Всего чеков', 'upsell_checks': 'Чеков с допродажей'}
    lines = [f"Сохранить показатели за {envelope['period_start']} — {envelope['period_end']} ({envelope['currency']})?"]
    lines += [label + ': ' + str(envelope['data'].get(key) if envelope['data'].get(key) is not None else 'не указано') for key, label in labels.items()]
    lines += ['Это общий итог за период. По дням он не распределяется и к дневным итогам не прибавляется.',
              'Подтверждение заменит ранее сохранённый итог за эти же даты и валюту.' if envelope['before_version'] else 'Сохранение — только после отдельного подтверждения.']
    return '\n'.join(lines)


def read(cursor, business_id, start, end):
    cursor.execute("""SELECT DISTINCT ON (target_id) after_json FROM finance_daily_events
        WHERE business_id=%s AND kind='period' AND after_json->>'period_start'<=%s AND after_json->>'period_end'>=%s
        ORDER BY target_id,created_at DESC,(after_json->>'version')::int DESC,id DESC""", (business_id, str(end), str(start)))
    return [_row(cursor, row)['after_json'] for row in cursor.fetchall()]


def spoken_values(message):
    from services.operator_finance_amounts import _AMOUNT, _number, verify_currency, verify_revenue
    values = {}
    for key, label in (('revenue', r'выручк[аиу]?'), ('refunds', r'возврат(?:ы|ов)?'), ('expenses', r'расход(?:ы|ов)?')):
        found = list(re.finditer(r'\b' + label + r'\s*(?:(?:до|после)\s+возвратов\s*)?(?:составил[аи]?\s*)?[:=]?\s*(' + _AMOUNT + r')', message, re.I))
        if key == 'refunds':
            found = [match for match in found if not re.search(r'(?:до|после)\s+$', message[:match.start()], re.I)]
        amounts = [match[1] for match in found]
        if len(amounts) > 1:
            raise ValueError('Укажите один общий итог каждого показателя за выбранный период.')
        if amounts:
            values[key] = str(_number(amounts[0].casefold()))
        elif re.search(r'\b' + label + r'\s+(?:пока\s+)?(?:не\s+знаю|неизвестн\w*|не\s+указан\w*)', message, re.I):
            values[key] = None
        elif re.search(r'\b' + label, message, re.I) and not (key == 'refunds' and re.search(r'(?:до|после)\s+возвратов', message, re.I)):
            raise ValueError('Не удалось прочитать сумму. Укажите выручку, возвраты и расходы точными числами.')
    for match in re.finditer(r'(' + _AMOUNT + r')\s+чек(?:а|ов)?\b(?P<upsell>\s+с\s+доп(?:родаж\w*|ом|ами)?)?', message, re.I):
        key = 'upsell_checks' if match['upsell'] else 'checks'
        if key in values:
            raise ValueError('Уточните общее число чеков и отдельно число чеков с допродажей.')
        values[key] = str(_number(match[1].casefold()))
    for key, pattern in (('checks', r'(?:всего\s+)?чек(?:а|ов)?\s*[:=]\s*'), ('upsell_checks', r'чек(?:а|ов)?\s+с\s+допродаж\w*\s*[:=]\s*')):
        match = re.search(pattern + '(' + _AMOUNT + ')', message, re.I)
        if match:
            if key in values:
                raise ValueError('Уточните количество чеков одним числом.')
            values[key] = str(_number(match[1].casefold()))
    args = verify_currency(message, {'kind': 'daily', 'values': values})
    if values.get('revenue') is not None:
        args = verify_revenue(message, args)
    return args


def route(cursor, *, business_id, user_id, message, channel, message_ref, subscription_access, orchestrator=None, previous_draft=None):
    from services.operator_core import _prepare_registered_capability_approval, operator_subscription_block
    from services.operator_finance_daily import observation
    blocked = operator_subscription_block(subscription_access, 'finance.daily.write')
    if blocked:
        return blocked, {}
    if re.match(r'\s*(?:если|например|допустим)', message, re.I) or '?' in message:
        return observation('Для внесения показателей укажите фактический период и суммы. Пример: «За сентябрь 2026 выручка 500 000 рублей, 200 чеков». Перед сохранением покажу проверку.', 'clarification_required'), {}
    try:
        finance_daily.authorize(cursor, business_id, user_id, True)
        config = finance_daily.settings(cursor, business_id)
        if previous_draft and not re.search(r'недел|месяц|\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}|за\s+[а-я]+\s+\d{4}', message, re.I):
            start,end=previous_draft['period_start'],previous_draft['period_end']
        else:
            start, end = dates(message, config.get('timezone'))
        args = spoken_values(message)
        if previous_draft:
            args['values']={**previous_draft['data'],**args['values']}
            args.setdefault('currency',previous_draft['currency'])
        envelope = prepare(cursor, business_id, user_id, {**args, 'period_start': start, 'period_end': end}, channel, message_ref)
        if previous_draft and (start,end,args.get('currency'))==(previous_draft['period_start'],previous_draft['period_end'],previous_draft['currency']) and envelope['before_fingerprint']!=previous_draft['before_fingerprint']:
            raise ValueError('Сохранённый итог изменился. Сообщите период и актуальные показатели заново, чтобы не заменить чужие изменения.')
    except PermissionError:
        import sys
        return observation(str(sys.exception()), 'blocked'), {}
    except ValueError:
        import sys
        return observation(str(sys.exception()), 'clarification_required'), {'capability': 'finance.period.clarification', 'source_message': message[:10000]}
    outcome = _prepare_registered_capability_approval(cursor=cursor, capability='finance.daily.write', tool_name='finance.prepare_period', business_id=business_id,
        user_id=user_id, channel=channel, message=message + '\n' + finance_daily.fingerprint(envelope), payload=envelope,
        backend_capability='finance.daily.apply_operator', orchestrator=orchestrator)
    if outcome.get('status') == 'approval_required':
        cursor.execute('SELECT name FROM businesses WHERE id=%s', (business_id,))
        outcome['chat_response'] = (_row(cursor, cursor.fetchone()).get('name') or 'Выбранный бизнес') + '\n' + preview(envelope)
        outcome['financial_draft'] = envelope
        outcome['approval']['summary'] = outcome['chat_response']
    pending={'capability':'finance.period.input','draft':envelope,'source_message':message[:10000]} if outcome.get('status')=='approval_required' else {}
    return outcome, pending


def recent(cursor, business_id):
    cursor.execute("""SELECT after_json FROM (SELECT DISTINCT ON (target_id) after_json,created_at
        FROM finance_daily_events WHERE business_id=%s AND kind='period'
        ORDER BY target_id,created_at DESC,(after_json->>'version')::int DESC,id DESC) latest
        ORDER BY created_at DESC LIMIT 12""", (business_id,))
    return [_row(cursor,row)['after_json'] for row in cursor.fetchall()]


def totals(values):
    from decimal import Decimal
    result={key:Decimal(values[key]) if values.get(key) is not None else None for key in finance_daily.FIELDS}
    revenue,refunds,checks,upsells=(result[key] for key in ('revenue','refunds','checks','upsell_checks'))
    result['net_revenue']=revenue-refunds if revenue is not None and refunds is not None else None
    result['average_check']=revenue/checks if revenue is not None and checks else None
    result['upsell_share']=upsells/checks*100 if upsells is not None and checks else None
    return result
