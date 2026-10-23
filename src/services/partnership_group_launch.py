"""Review a saved collection, then atomically schedule its existing native campaigns.

Preview is read-only. Confirmation calls the same review/approval functions as an
individual campaign; it never dispatches a provider message or changes send limits.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from psycopg2.extras import Json
from services import partnership_prepared_campaigns as prepared
from services.partnership_source_collections import load_collections
from services.operator_conversations import _row

MOSCOW = ZoneInfo('Europe/Moscow')


def parse_start(value, now):
    if not isinstance(value, str):
        raise ValueError('Укажите дату и время начала для обоих каналов.')
    try:
        start = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Проверьте дату и время начала.')
    if start.tzinfo is None or start < now + timedelta(minutes=5):
        raise ValueError('Начало должно быть не раньше чем через 5 минут. Время — московское.')
    if start > now + timedelta(days=30):
        raise ValueError('Выберите начало в ближайшие 30 дней.')
    return start.astimezone(MOSCOW)


def office_time(value):
    value = value.astimezone(MOSCOW)
    if value.hour >= 18:
        value = (value + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    if value.hour < 10:
        value = value.replace(hour=10, minute=0, second=0, microsecond=0)
    while value.weekday() >= 5:
        value = (value + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    return value


def schedule_items(items, options, now):
    if not isinstance(options, dict):
        raise ValueError('Укажите расписание группы.')
    interval = options.get('interval_minutes', 5)
    if isinstance(interval, bool) or not isinstance(interval, int) or not 3 <= interval <= 60:
        raise ValueError('Интервал между компаниями — от 3 до 60 минут.')
    starts = {channel: parse_start(options.get(channel + '_start'), now) for channel in ['telegram', 'email']}
    if any(office_time(value) != value for value in starts.values()):
        raise ValueError('Выберите рабочий день, с 10:00 до 18:00 по Москве.')
    ordered = sorted(items, key=lambda item: (item['touches'][0]['channel'] != 'telegram', (item.get('name') or '').casefold(), item['id']))
    counters = {'telegram': 0, 'email': 0}
    next_start = dict(starts)
    first_telegram_end = None
    result = []
    for item in ordered:
        channel = item['touches'][0]['channel']
        if channel not in counters or any(touch['channel'] != channel for touch in item['touches']):
            raise ValueError('В группе нужны отдельные Telegram-цепочки и отдельные почтовые цепочки.')
        start = next_start[channel]
        next_start[channel] = office_time(start + timedelta(minutes=interval))
        counters[channel] += 1
        if channel == 'telegram':
            first_telegram_end = start
        if channel == 'email' and first_telegram_end and start < first_telegram_end + timedelta(minutes=interval):
            raise ValueError('Почта должна начинаться после последнего первого обращения в Telegram с учётом интервала.')
        touches = item['touches']
        if not touches or [touch['sequence_index'] for touch in touches] != list(range(len(touches))):
            raise ValueError('Нарушен порядок касаний. Откройте цепочку компании.')
        base = touches[0]['scheduled_at']
        if isinstance(base, str):
            base = datetime.fromisoformat(base.replace('Z', '+00:00'))
        scheduled = []
        for touch in touches:
            original = touch['scheduled_at']
            if isinstance(original, str):
                original = datetime.fromisoformat(original.replace('Z', '+00:00'))
            offset = original.date() - base.date()
            if offset.days < 0:
                raise ValueError('Нарушен порядок дат в сохранённой цепочке.')
            date = office_time(start + offset)
            if scheduled and date <= datetime.fromisoformat(scheduled[-1]['scheduled_at']):
                raise ValueError('Касания одной компании должны идти в разные дни.')
            scheduled.append({**touch, 'scheduled_at': date.isoformat()})
        result.append({**item, 'touches': scheduled})
    return result, counters



def default_schedule(items, now):
    first = office_time(now.astimezone(MOSCOW).replace(second=0, microsecond=0) + timedelta(minutes=15))
    first = office_time(first + timedelta(minutes=(-first.minute) % 5))
    after_telegram = first
    for item in items:
        if item['touches'][0]['channel'] == 'telegram':
            after_telegram = office_time(after_telegram + timedelta(minutes=5))
    return {'telegram_start': first.isoformat(), 'email_start': after_telegram.isoformat(), 'interval_minutes': 5}


def authorize(cursor, user, business_id):
    from core.auth_helpers import session_allows_business
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    if not session_allows_business(user, business_id):
        raise PermissionError('Нет доступа к этому бизнесу в текущей сессии.')
    _, access = authorize_actor(cursor, str(user['user_id']), business_id, check_subscription=False, require_write=True)
    if not capability_access_payload(access, 'partnerships').get('allowed'):
        raise PermissionError('Нет доступа к партнёрствам.')


def sender_contexts(cursor, sender_ids):
    if not sender_ids:
        raise ValueError('Не выбраны отправители.')
    cursor.execute('''SELECT s.id,s.scope_type,s.business_id,s.status,s.outreach_enabled,s.health_status,
        s.capabilities_json,s.external_account_id,s.display_name,s.sender_identity,
        p.outreach_enabled AS telegram_outreach_enabled
        FROM outreach_sender_accounts s LEFT JOIN telegram_account_permissions p ON p.account_id=s.external_account_id
        WHERE s.id IN (''' + ','.join(['%s'] * len(sender_ids)) + ')', tuple(sorted(sender_ids)))
    result = {}
    for row in cursor.fetchall():
        sender = _row(cursor, row)
        label = sender.get('sender_identity') or sender.get('display_name')
        if sender.get('external_account_id') and not sender.get('sender_identity'):
            from core.telegram_userbot import load_userbot_account
            account = load_userbot_account(cursor, account_id=str(sender['external_account_id'])) or {}
            phone = account.get('phone') or ''
            label = (sender.get('display_name') or 'Telegram LocalOS') + (' · …' + phone[-4:] if phone else '')
        sender['label'] = label or 'Отправитель не указан'
        result[str(sender['id'])] = sender
    return result


def build_preview(cursor, *, user, business_id, collection_id, options, now=None):
    from services.outreach_campaign_service import runtime_touch_channel_status
    from services.outreach_safety_service import sender_scope_preflight_reason
    authorize(cursor, user, business_id)
    rows = load_collections(cursor, business_id=business_id, task_id=collection_id)
    if not rows:
        raise LookupError('Подборка недоступна или не найдена.')
    collection = rows[0]
    state = collection.get('result_json') or {}
    if state.get('reviewed_launch'):
        raise ValueError('Эта подборка уже подтверждена. Откройте её отправку и статусы; повторный запуск запрещён.')
    lead_ids = list(dict.fromkeys(state.get('lead_ids') or []))
    if not lead_ids or len(lead_ids) > 100:
        raise ValueError('Для проверки нужна подборка от 1 до 100 компаний.')
    items = prepared.list_prepared(cursor, business_id=business_id, user_id=str(user['user_id']), lead_ids=lead_ids)
    if len(items) != len(lead_ids) or {item['lead_id'] for item in items} != set(lead_ids):
        raise ValueError('Не у всех компаний есть сохранённая цепочка. Сначала завершите подготовку.')
    sender_ids = set()
    recipients = set()
    companies = set()
    for item in items:
        if (item.get('policy_json') or {}).get('stop_on_reply') is not True:
            raise ValueError('Для этой группы нужна остановка повторных касаний при ответе.')
        if item['status'] != 'draft' or item.get('hold_reason'):
            raise ValueError(item.get('hold_reason') or 'В подборке есть уже запущенная цепочка. Повторный запуск запрещён.')
        if item.get('company_id') in companies:
            raise ValueError('В группе повторяется компания. Проверьте подборку.')
        companies.add(item.get('company_id'))
        item['touches'] = prepared.load_touches(cursor, item['id'])
        if not item['touches']:
            raise ValueError('Есть пустая цепочка.')
        contact = prepared.normalized(item['touches'][0]['recipient'])
        if not contact or contact in recipients:
            raise ValueError('В группе повторяется получатель или не указан контакт.')
        recipients.add(contact)
        for touch in item['touches']:
            if touch['status'] != 'draft' or not touch.get('sender_account_id'):
                raise ValueError('Есть недоступное касание или не выбран отправитель.')
            if not set((touch.get('quality_gate_json') or {}).get('reason_codes') or []).issubset(prepared.COPY_ONLY_REASONS):
                raise ValueError('Есть ошибки фактов или безопасности. Откройте сообщения компании.')
            sender_ids.add(str(touch['sender_account_id']))
    senders = sender_contexts(cursor, sender_ids)
    for item in items:
        for touch in item['touches']:
            sender = senders.get(str(touch['sender_account_id']))
            if not sender:
                raise ValueError('Отправитель больше недоступен.')
            context = {**touch, 'sender_status': sender['status'], 'sender_health_status': sender['health_status'],
                'sender_outreach_enabled': sender['outreach_enabled'], 'sender_capabilities_json': sender['capabilities_json'],
                'telegram_outreach_enabled': sender.get('telegram_outreach_enabled')}
            if runtime_touch_channel_status(context) != 'ready':
                raise ValueError('Канал или разрешение отправителя не готовы: ' + sender['label'])
            scope_context = {**item, **touch, 'scope_type': 'business', 'business_id': business_id,
                'sender_scope_type': sender['scope_type'], 'sender_business_id': sender['business_id']}
            if sender_scope_preflight_reason(scope_context):
                raise ValueError('Отправитель не соответствует бизнесу и режиму обращения.')
            touch['sender_label'] = sender['label']
    now = now or datetime.now(timezone.utc)
    if options is not None and not isinstance(options, dict):
        raise ValueError('Проверьте расписание.')
    first_only = (options or {}).get('first_touch_only', False)
    if not isinstance(first_only, bool):
        raise ValueError('Выберите первые обращения или всю цепочку.')
    if first_only:
        items = [{**item, 'touches': item['touches'][:1]} for item in items]
    if options is None or set(options) <= {'first_touch_only'}:
        options = {**default_schedule(items, now), **(options or {})}
    scheduled, counts = schedule_items(items, options, now)
    enabled = (os.getenv('OUTREACH_DISPATCH_ENABLED') or '').lower() in {'true','1','yes','on'}
    cohort = {value.strip() for value in (os.getenv('OUTREACH_DISPATCH_BUSINESS_IDS') or '').split(',') if value.strip()}
    runtime_ready = enabled and business_id in cohort
    public_items = [{
        'campaign_id': str(item['id']), 'lead_id': str(item['lead_id']), 'name': item['name'], 'address': item.get('address'),
        'review_digest': item['review_digest'],
        'touches': [{key: touch.get(key) for key in ['id','sequence_index','channel','subject','generated_text','recipient','contact_source','sender_account_id','sender_label','scheduled_at']} for touch in item['touches']],
    } for item in scheduled]
    result = {'collection_id': collection_id, 'business_id': business_id, 'timezone': 'Europe/Moscow',
        'counts': counts, 'items': public_items, 'company_count': len(items),
        'touch_count': sum(len(item['touches']) for item in items), 'schedule': options,
        'runtime_ready': runtime_ready, 'messages_sent': 0,
        'valid_until': (min(datetime.fromisoformat(item['touches'][0]['scheduled_at']) for item in scheduled) - timedelta(minutes=5)).isoformat(),
        'warning': None if runtime_ready else 'Фоновая отправка для этой точки выключена. Подтверждение запуска недоступно; подключения и лимиты не изменены.'}
    result['digest'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


def confirm_launch(cursor, *, user, business_id, collection_id, options, digest, reviewed, confirmed):
    from services.outreach_campaign_service import approve_campaign
    authorize(cursor, user, business_id)
    if reviewed is not True or confirmed is not True:
        raise ValueError('Отдельно подтвердите проверку текстов и постановку сообщений на отправку.')
    cursor.execute("SELECT result_json FROM operator_async_jobs WHERE id=%s AND business_id=%s AND kind='partnership_source_collection' AND status='completed' FOR UPDATE", (collection_id,business_id))
    row = _row(cursor, cursor.fetchone())
    if not row:
        raise LookupError('Подборка не найдена.')
    receipt = (row.get('result_json') or {}).get('reviewed_launch')
    if receipt:
        if receipt.get('digest') != digest:
            raise ValueError('Подборка уже подтверждена с другим расписанием.')
        return {**receipt, 'idempotent': True, 'messages_sent': 0}
    # Lock campaigns/touches in a deterministic order before re-reading the preview.
    lead_ids = (row.get('result_json') or {}).get('lead_ids') or []
    if not isinstance(lead_ids, list) or not 1 <= len(lead_ids) <= 100:
        raise ValueError('Подборка изменилась. Повторите проверку.')
    cursor.execute('SELECT c.id FROM outreach_campaigns c WHERE c.business_id=%s AND c.lead_id IN (' + ','.join(['%s'] * len(lead_ids)) + ') ORDER BY c.id FOR UPDATE', (business_id, *lead_ids))
    cursor.fetchall()
    preview = build_preview(cursor, user=user, business_id=business_id, collection_id=collection_id, options=options)
    if not digest or preview['digest'] != digest:
        raise ValueError('Получатель, текст, отправитель или расписание изменились. Повторите общую проверку.')
    if not preview['runtime_ready']:
        raise ValueError(preview['warning'])
    batch_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO outreachsendbatches(id,batch_date,daily_limit,status,created_by,created_at,updated_at) VALUES(%s,%s,%s,'draft',%s,NOW(),NOW())", (batch_id,datetime.now(MOSCOW).date(),preview['company_count'],str(user['user_id'])))
    for item in preview['items']:
        campaign_id = item['campaign_id']
        cursor.execute('SELECT id FROM outreach_campaign_touches WHERE campaign_id=%s ORDER BY id FOR UPDATE',(campaign_id,))
        cursor.fetchall()
        prepared.review_copy(cursor, business_id=business_id, user=user, campaign_id=campaign_id, digest=item['review_digest'])
        for touch in item['touches']:
            cursor.execute("UPDATE outreach_campaign_touches SET scheduled_at=%s,updated_at=NOW() WHERE id=%s AND campaign_id=%s AND status='draft'",(touch['scheduled_at'],touch['id'],campaign_id))
            if cursor.rowcount != 1:
                raise ValueError('Касание изменилось во время подтверждения. Ничего не запущено.')
        approve_campaign(cursor, campaign_id, user_id=str(user['user_id']), reviewed_batch_id=batch_id, first_touch_only=(options or {}).get('first_touch_only', False))
    cursor.execute("UPDATE outreachsendbatches SET status='approved',approved_by=%s,updated_at=NOW() WHERE id=%s AND status='draft'", (str(user['user_id']),batch_id))
    receipt = {'digest':digest,'batch_id':batch_id,'company_count':preview['company_count'],'touch_count':preview['touch_count'],
        'counts':preview['counts'],'schedule':options,'approved_by':str(user['user_id']),'approved_at':datetime.now(timezone.utc).isoformat(),'status':'scheduled'}
    cursor.execute("UPDATE operator_async_jobs SET result_json=jsonb_set(COALESCE(result_json,'{}'),'{reviewed_launch}',%s),updated_at=NOW() WHERE id=%s AND business_id=%s",(Json(receipt),collection_id,business_id))
    return {**receipt,'messages_sent':0}
