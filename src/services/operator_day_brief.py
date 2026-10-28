"""Owner-reviewed daily focus on existing conversations, actions and delivery jobs."""
import json
import os
import re
import uuid
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
from services.operator_conversations import _row, get_or_create_operator_conversation, append_operator_message
from services import operator_workday, work_journal, work_recommendations


def delivery_enabled():
    return os.getenv('OPERATOR_DAY_BRIEF_DELIVERY_ENABLED', '').lower() in {'1', 'true'}


def authorize(cursor, business, user, owner=False):
    if not operator_workday.enabled(business):
        raise PermissionError('Рабочие функции не включены для этого бизнеса.')
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    _, access = authorize_actor(cursor, user, business)
    from services.team_work_access import allowed
    if not allowed(access):
        raise PermissionError('Планёрка команды недоступна на текущем тарифе бизнеса.')
    return work_journal.scope(cursor, business, user, write=owner, owner_only=owner)


def members(cursor, business):
    cursor.execute('''SELECT u.id,u.name,u.telegram_id,m.max_id,m.notifications_enabled
        FROM users u LEFT JOIN max_identities m ON m.user_id=u.id AND m.revoked_at IS NULL
        WHERE u.is_active=TRUE AND EXISTS(SELECT 1 FROM businesses b WHERE b.id=%s AND
          (u.id=b.owner_id OR EXISTS(SELECT 1 FROM business_members bm WHERE bm.business_id=b.id AND bm.user_id=u.id AND bm.status='active')
           OR EXISTS(SELECT 1 FROM network_members nm WHERE nm.network_id=b.network_id AND nm.user_id=u.id AND nm.status='active')
           OR EXISTS(SELECT 1 FROM networks n WHERE n.id=b.network_id AND n.owner_id=u.id))) ORDER BY u.name,u.id''', (business,))
    people = [_row(cursor, row) for row in cursor.fetchall()]
    for person in people:
        person['name'] = str(person.get('name') or 'Сотрудник ' + str(person['id'])[:8])
    return people


def draft(cursor, business, user, day=None, identifier=None, lock=False):
    suffix = ' FOR UPDATE' if lock else ''
    if identifier:
        cursor.execute("SELECT * FROM operatorconversations WHERE id=%s AND business_id=%s AND user_id=%s AND transport_key LIKE 'day-brief:%%'" + suffix, (identifier, business, user))
    else:
        cursor.execute("SELECT * FROM operatorconversations WHERE business_id=%s AND user_id=%s AND channel='web' AND transport_key=%s" + suffix, (business, user, 'day-brief:' + day))
    row = _row(cursor, cursor.fetchone())
    return {'id': str(row['id']), **(row.get('input_context_json') or {}).get('day_brief', {})} if row else {}


def text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(label + ': укажите текст до ' + str(limit) + ' символов.')
    return value.strip()


def save(cursor, *, business, user, payload, channel='web'):
    authorize(cursor, business, user, owner=True)
    day = work_journal.local_day(cursor, business, payload.get('date'))
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('day-brief:' + business + ':' + user + ':' + day,))
    current = draft(cursor, business, user, day=day, lock=True)
    request_id = str(payload.get('request_id') or '')
    uuid.UUID(request_id)
    focus = text(payload.get('focus'), 1500, 'Фокус дня')
    targets = payload.get('recipients', [])
    if not isinstance(targets, list) or len(targets) > 20:
        raise ValueError('Выберите до 20 сотрудников.')
    available = {str(row['id']): row for row in members(cursor, business)}
    clean = []
    for target in targets:
        if not isinstance(target, dict) or str(target.get('user_id')) not in available:
            raise PermissionError('Сотрудник не имеет активного доступа к бизнесу.')
        uid = str(target['user_id'])
        if any(row['user_id'] == uid for row in clean):
            raise ValueError('Сотрудник выбран дважды.')
        platforms = target.get('platforms', [])
        if not isinstance(platforms, list) or not platforms or any(not isinstance(p, str) or p not in {'telegram', 'max'} for p in platforms) or len(set(platforms)) != len(platforms):
            raise ValueError('Выберите Telegram, MAX или оба мессенджера.')
        tasks = target.get('tasks', [])
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 10:
            raise ValueError('Укажите от 1 до 10 задач сотруднику.')
        clean.append({'user_id': uid, 'platforms': platforms,
            'tasks': [{'id': str(uuid.uuid5(uuid.NAMESPACE_URL, uid + ':' + str(i) + ':' + text(task.get('text') if isinstance(task, dict) else task, 1500, 'Задача'))),
                       'text': text(task.get('text') if isinstance(task, dict) else task, 1500, 'Задача'), 'done': False} for i, task in enumerate(tasks)]})
    fingerprint = work_journal.digest([day, focus, clean])
    if current.get('request_id') == request_id:
        if current.get('request_hash') != fingerprint:
            raise ValueError('Повтор запроса содержит другой фокус или задачи.')
        return {**current, 'idempotent': True}
    if payload.get('version', 0) != current.get('version', 0):
        raise ValueError('Планёрка уже изменена. Обновите её перед сохранением.')
    if not current:
        record = get_or_create_operator_conversation(cursor, business_id=business, user_id=user, channel='web', transport_key='day-brief:' + day)
        identifier = str(record['id'])
        # The storage conversation must not become the bot's active discussion.
        cursor.execute("UPDATE operatorconversations SET status='handoff_prepared' WHERE id=%s", (identifier,))
    else:
        identifier = current['id']
    value = {'date': day, 'focus': focus, 'recipients': clean, 'version': current.get('version', 0) + 1,
        'status': 'draft', 'request_id': request_id, 'request_hash': fingerprint}
    cursor.execute('UPDATE operatorconversations SET input_context_json=%s::jsonb,updated_at=NOW() WHERE id=%s',
        (json.dumps({'day_brief': value}, ensure_ascii=False), identifier))
    append_operator_message(cursor, conversation_id=identifier, business_id=business, user_id=user, role='operator',
        content=focus, capability='work.day_brief', status='draft', result={'before': current, 'after': value, 'source_channel': channel})
    return {'id': identifier, **value}


def tips(cursor, business, user, day):
    services = work_recommendations.catalog(cursor, business)
    policy = work_recommendations.policy(cursor, business)
    matrix = policy.get('matrix_json')
    if matrix is None:
        matrix = work_recommendations.matrix(cursor, business).get('matrix_json')
    rules = policy.get('rules_json') or []
    cursor.execute('SELECT master_id FROM business_master_bindings WHERE business_id=%s AND user_id=%s', (business, user))
    master = _row(cursor, cursor.fetchone()).get('master_id')
    if not master and any(rule.get('master_id') for rule in rules):
        return [], 'Уточните привязку сотрудника к мастеру для персональных правил.'
    from services.finance_daily import settings
    zone = settings(cursor, business).get('timezone')
    if not zone:
        raise ValueError('Укажите часовой пояс бизнеса.')
    moment = datetime.now(ZoneInfo(zone))
    if day != moment.date().isoformat() and any(rule.get('starts_at') or rule.get('ends_at') for rule in rules):
        return [], 'Для этой даты есть правила по времени. Проверьте их перед предложением услуги.'
    selected = []
    available = {str(row['id']): row for row in services}
    for row in (matrix or {}).get('upsell_matrix') or []:
        main = available.get(str(row.get('main_service_id')))
        if not main:
            continue
        for addon in work_recommendations.select(services, matrix, rules, main['id'], master, None, now=moment):
            wording = addon.get('master_script') or addon.get('admin_script') or 'Формулировка предложения пока не настроена.'
            selected.append({'main_service': main['name'], 'service': addon['service_name'], 'wording': wording,
                'reason': addon['reason'], 'time_verified': False})
            if len(selected) == 3:
                return selected, 'Перед предложением проверьте уместность и свободное время. Допродажа не обязательна.'
    return selected, 'Перед предложением проверьте уместность и свободное время. Допродажа не обязательна.' if selected else 'Согласованных подходящих связок пока нет. Настройте их в разделе «Средний чек».'


def render(day, focus, tasks, suggestions, note, business_name):
    lines = ['Планёрка · ' + business_name, 'На ' + day, 'Фокус дня: ' + focus, '', 'Ваши задачи:']
    lines.extend(str(i + 1) + '. ' + task['text'] for i, task in enumerate(tasks))
    lines.extend(['', 'Что можно предложить клиенту:'])
    lines.extend(item['main_service'] + ' → ' + item['service'] + '\n' + item['wording'] for item in suggestions)
    lines.append(note)
    return '\n'.join(lines)


def preview(cursor, *, business, user, identifier, version):
    authorize(cursor, business, user, owner=True)
    if not identifier or type(version) is not int:
        raise ValueError('Укажите сохранённую планёрку и её версию.')
    uuid.UUID(str(identifier))
    value = draft(cursor, business, user, identifier=identifier)
    if not value or value['version'] != version:
        raise ValueError('Планёрка изменилась. Проверьте актуальную версию.')
    if not value['recipients']:
        raise ValueError('Выберите сотрудников и задачи в планёрке.')
    cursor.execute('SELECT name FROM businesses WHERE id=%s', (business,))
    business_name = str(_row(cursor, cursor.fetchone()).get('name') or 'Выбранный бизнес')
    available = {str(row['id']): row for row in members(cursor, business)}
    messages = []
    for target in value['recipients']:
        member = available.get(target['user_id'])
        if not member:
            raise PermissionError('Доступ сотрудника отозван. Проверьте получателей.')
        suggestions, note = tips(cursor, business, target['user_id'], value['date'])
        body = render(value['date'], value['focus'], target['tasks'], suggestions, note, business_name)
        if len(body.encode('utf-16-le')) // 2 > 3500:
            raise ValueError('Сообщение слишком длинное. Сократите фокус или задачи сотрудника.')
        bindings = {}
        for platform in target['platforms']:
            binding = member.get('telegram_id') if platform == 'telegram' else member.get('max_id') if member.get('notifications_enabled') else None
            if not binding:
                raise ValueError(member['name'] + ': подключите выбранный мессенджер и разрешите уведомления.')
            bindings[platform] = str(binding)
        messages.append({'user_id': target['user_id'], 'name': member['name'], 'bindings': bindings,
            'text': body, 'tasks': target['tasks'], 'tips': suggestions, 'note': note})
    payload = {'business_id': business, 'business_name': business_name, 'record_id': identifier, 'version': version, 'date': value['date'], 'messages': messages,
        'delivery_enabled': delivery_enabled()}
    return payload


def public_preview(payload):
    return {**payload, 'messages': [{key: item for key, item in row.items() if key != 'bindings'} |
            {'platforms': list(row['bindings'])} for row in payload['messages']]}


def prepare(cursor, *, business, user, identifier, version):
    payload = preview(cursor, business=business, user=user, identifier=identifier, version=version)
    lines = ['Бизнес: ' + payload['business_name'], 'Проверьте задачи и подсказки каждому сотруднику.']
    lines.append('После подтверждения появятся в их кабинетах.' + (' Уведомления будут поставлены в очередь.' if payload['delivery_enabled'] else ' Доставка в мессенджеры пока выключена.'))
    for row in payload['messages']:
        lines.extend(['\nПолучатель: ' + row['name'] + ' · ' + ', '.join(row['bindings']), row['text']])
    return {'status': 'approval_required', 'capability': 'work.day_brief', 'chat_response': '\n\n'.join(lines),
        'day_brief_preview': public_preview(payload), 'approval': {'envelope': payload}}


def apply(cursor, *, business, user, envelope):
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('day-brief:' + business + ':' + user + ':' + envelope['date'],))
    fresh = preview(cursor, business=business, user=user, identifier=envelope['record_id'], version=envelope['version'])
    if fresh != envelope:
        raise ValueError('Получатели, правила допродаж или доставка изменились. Проверьте действие заново.')
    value = draft(cursor, business, user, identifier=envelope['record_id'], lock=True)
    from services.operator_async_jobs import create_operator_async_job
    actions = []
    keep = [str(uuid.uuid5(uuid.NAMESPACE_URL, 'day-brief:' + value['id'] + ':' + str(value['version']) + ':' + row['user_id'])) for row in fresh['messages']]
    cursor.execute("UPDATE journey_actions SET status='superseded',updated_at=NOW() WHERE business_id=%s AND entity_type='operator_colleague' AND action_type='day_brief' AND entity_id=%s AND NOT(id::text=ANY(%s))", (business, value['id'], keep))
    for row in fresh['messages']:
        identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, 'day-brief:' + value['id'] + ':' + str(value['version']) + ':' + row['user_id']))
        key = 'day-brief:' + identifier
        data = {'record_id': value['id'], 'owner_id': user, 'revision': value['version'], 'date': value['date'],
            'focus': value['focus'], 'tasks': row['tasks'], 'tips': row['tips'], 'note': row['note']}
        # Same tasks across Telegram/MAX; each delivery has its own guarded job.
        cursor.execute("UPDATE journey_actions SET status='superseded',updated_at=NOW() WHERE business_id=%s AND entity_type='operator_colleague' AND action_type='day_brief' AND entity_id=%s AND user_id=%s AND id<>%s AND status<>'superseded'", (business, value['id'], row['user_id'], identifier))
        cursor.execute('''INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,entity_id,action_type,title,description,cta_label,cta_target_json,payload_json,dedupe_key,due_at)
            VALUES(%s,%s,%s,'work_journal','operator_colleague',%s,'day_brief',%s,%s,'Открыть задачи',%s::jsonb,%s::jsonb,%s,NOW()) ON CONFLICT(id) DO NOTHING''',
            (identifier, business, row['user_id'], value['id'], 'Планёрка на ' + value['date'], row['text'],
             json.dumps({'screen': 'work_journal', 'item_type': 'day_brief', 'item_id': identifier}), json.dumps(data, ensure_ascii=False), key))
        actions.append(identifier)
        if fresh['delivery_enabled']:
            for platform, binding in row['bindings'].items():
                create_operator_async_job(cursor, user_id=user, business_id=business, action_id=None, kind='operator_colleague_send',
                    payload={'briefing_delivery': {'action_id': identifier, 'record_id': value['id'], 'version': value['version'],
                        'recipient_user_id': row['user_id'], 'platform': platform, 'binding': binding, 'text': row['text'], 'state': 'queued'}},
                    idempotency_key='day-brief:' + identifier + ':' + platform, stage='Уведомление о задачах', max_attempts=1)
    value.update(status='assigned')
    cursor.execute('UPDATE operatorconversations SET input_context_json=%s::jsonb WHERE id=%s', (json.dumps({'day_brief': {k: v for k, v in value.items() if k != 'id'}}, ensure_ascii=False), value['id']))
    return {'status': 'completed', 'capability': 'work.day_brief', 'chat_response': 'Задачи доступны сотрудникам в кабинетах. ' + ('Уведомления в очереди; доставка ещё не подтверждена.' if fresh['delivery_enabled'] else 'Уведомления в мессенджеры выключены.'), 'action_ids': actions, 'external_writes_performed': False}


def assignments(cursor, business, user, owner=False, day=None):
    authorize(cursor, business, user, owner=owner)
    cursor.execute("SELECT id,user_id,status,version,payload_json FROM journey_actions WHERE business_id=%s AND entity_type='operator_colleague' AND action_type='day_brief' AND status NOT IN ('cancelled','superseded') AND (%s OR user_id=%s) AND (%s::text IS NULL OR payload_json->>'date'=%s) ORDER BY created_at DESC LIMIT 100", (business, owner, user, day, day))
    return [_row(cursor, row) for row in cursor.fetchall()]


def complete_task(cursor, *, business, user, action_id, task_id, version, done):
    actor = authorize(cursor, business, user)
    if actor['role'] == 'viewer':
        raise PermissionError('Нет права менять задачи.')
    if type(done) is not bool:
        raise ValueError('Укажите состояние задачи.')
    cursor.execute("SELECT * FROM journey_actions WHERE id=%s AND business_id=%s AND user_id=%s AND entity_type='operator_colleague' AND action_type='day_brief' FOR UPDATE", (action_id, business, user))
    row = _row(cursor, cursor.fetchone())
    if not row or row['status'] in {'superseded', 'cancelled'}:
        raise PermissionError('Задача недоступна.')
    items = row['payload_json']['tasks']
    task = next((item for item in items if item['id'] == task_id), None)
    if not task:
        raise ValueError('Задача не найдена.')
    if row['version'] != version:
        if task['done'] == done:
            return {'status': 'completed', 'idempotent': True}
        raise ValueError('Состояние уже изменилось. Обновите задачи.')
    task['done'] = done
    status = 'completed' if all(item['done'] for item in items) else 'in_progress'
    cursor.execute('UPDATE journey_actions SET payload_json=%s::jsonb,status=%s,version=version+1,updated_at=NOW(),completed_at=CASE WHEN %s THEN NOW() ELSE NULL END WHERE id=%s',
        (json.dumps(row['payload_json'], ensure_ascii=False), status, status == 'completed', action_id))
    return {'status': 'completed'}


def process_job(job):
    """Existing colleague job; its persisted payload is the no-blind-retry fence."""
    from database_manager import DatabaseManager
    from services import operator_colleagues
    from services.max_transport import MaxTransport, MaxTransportError
    db = DatabaseManager()
    try:
        c = db.conn.cursor()
        c.execute('SELECT payload_json FROM operator_async_jobs WHERE id=%s AND business_id=%s FOR UPDATE', (job['id'], job['business_id']))
        stored = _row(c, c.fetchone())
        value = (stored.get('payload_json') or {}).get('briefing_delivery')
        if not value:
            raise ValueError('Уведомление не найдено.')
        if value['state'] == 'sent':
            return {'status': 'completed', 'delivery_state': 'sent', 'provider_message_id': value['provider_message_id']}
        if value['state'] != 'queued':
            return {'status': 'blocked', 'delivery_state': value['state'], 'chat_response': 'Результат отправки требует проверки. Автоматического повтора нет.'}
        business, user = job['business_id'], job['user_id']
        authorize(c, business, user, owner=True)
        current = draft(c, business, user, identifier=value['record_id'])
        if not current or current['version'] != value['version'] or current['status'] != 'assigned':
            raise ValueError('Планёрка изменена. Отправка остановлена.')
        available = {str(row['id']): row for row in members(c, business)}
        recipient = available.get(value['recipient_user_id']) or {}
        platform = value['platform']
        binding = recipient.get('telegram_id') if platform == 'telegram' else recipient.get('max_id') if recipient.get('notifications_enabled') else None
        if not binding or str(binding) != value['binding']:
            raise PermissionError('Получатель или подключение изменились. Отправка остановлена.')
        if not delivery_enabled():
            raise PermissionError('Доставка планёрок пока выключена.')
        c.execute("SELECT status,payload_json FROM journey_actions WHERE id=%s AND business_id=%s AND user_id=%s", (value['action_id'], business, value['recipient_user_id']))
        action = _row(c, c.fetchone())
        if not action or action['status'] in {'superseded', 'cancelled'}:
            raise ValueError('Задачи больше не действуют.')
        # Recompute wording/rules before dispatch. Never send a now-forbidden offer.
        suggestions, note = tips(c, business, value['recipient_user_id'], current['date'])
        if suggestions != action['payload_json']['tips'] or note != action['payload_json']['note']:
            raise ValueError('Правила допродаж изменились. Подготовьте планёрку заново.')
        from services.operator_work_handoff import mobile_work_url
        url = mobile_work_url(business, value['action_id'], platform, 'work_journal', 'day_brief')
        if platform == 'telegram':
            if not os.getenv('TELEGRAM_BOT_TOKEN'):
                raise ValueError('Telegram не настроен.')
            markup = {'inline_keyboard': [[{'text': 'Мои задачи дня', 'web_app': {'url': url}}]]}
        else:
            if not os.getenv('MAX_BOT_TOKEN') or not os.getenv('MAX_BOT_USERNAME'):
                raise ValueError('MAX не настроен.')
            from services.max_owner_dialogues import platform_url
            markup = [{'type': 'inline_keyboard', 'payload': {'buttons': [[{'type': 'link', 'text': 'Мои задачи дня', 'url': platform_url(url, web_app=True)}]]}}]
        value['state'] = 'unknown'
        def persist():
            c.execute('UPDATE operator_async_jobs SET payload_json=%s::jsonb WHERE id=%s', (json.dumps(stored['payload_json'], ensure_ascii=False), job['id']))
            db.conn.commit()
        persist()
        try:
            if platform == 'max':
                body = MaxTransport().send(binding, value['text'], attachments=markup)
                message_id = body['message']['body']['mid']
            else:
                response = operator_colleagues.requests.post('https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/sendMessage',
                    json={'chat_id': str(binding), 'text': value['text'], 'reply_markup': markup}, timeout=(10, 30),
                    **operator_colleagues.build_requests_proxy_kwargs())
                body = response.json()
                if response.status_code != 200 or not body.get('ok'):
                    value['state'] = 'unknown' if response.status_code >= 500 or response.status_code in {408, 409} else 'failed'
                    persist()
                    return {'status': 'blocked', 'delivery_state': value['state']}
                message_id = body['result']['message_id']
            value.update(state='sent', provider_message_id=str(message_id))
            persist()
            return {'status': 'completed', 'delivery_state': 'sent', 'provider_message_id': str(message_id)}
        except MaxTransportError:
            import sys
            if not sys.exception().uncertain:
                value['state'] = 'failed'
                persist()
            return {'status': 'blocked', 'delivery_state': value['state']}
        except (operator_colleagues.requests.RequestException, ValueError, KeyError, TypeError):
            return {'status': 'blocked', 'delivery_state': 'unknown'}
    finally:
        db.close()


def delivery_states(cursor, business, rows):
    """Only metadata for already authorized assignments; never recipient bindings."""
    if not rows:return []
    cursor.execute("""SELECT status,payload_json->'briefing_delivery' delivery FROM operator_async_jobs
        WHERE business_id=%s AND kind='operator_colleague_send'
          AND payload_json->'briefing_delivery'->>'action_id'=ANY(%s)
        ORDER BY created_at""",(business,[str(row['id']) for row in rows]))
    result=[]
    for item in cursor.fetchall():
        job=_row(cursor,item);value=job['delivery'];state=value.get('state','unknown')
        if state=='sent' and not value.get('provider_message_id'):state='unknown'
        if state=='queued' and job['status'] in {'failed','cancelled','completed'}:state='stopped'
        result.append({'action_id':value['action_id'],'platform':value['platform'],'state':state})
    return result


def delivery_label(state):
    return {'sent':'Отправлено','queued':'В очереди','failed':'Не отправлено',
            'stopped':'Доставка остановлена','unknown':'Результат доставки неизвестен; повторная отправка остановлена'}.get(state,'Проверьте доставку')


def overview(cursor, *, business, user, day=None, item_id=None):
    actor = authorize(cursor, business, user)
    owner = actor['role'] == 'owner'
    if item_id:
        uuid.UUID(str(item_id))
        selected = draft(cursor, business, user, identifier=item_id) if owner else {}
        if selected:
            day = selected['date']
        else:
            cursor.execute("SELECT payload_json FROM journey_actions WHERE id=%s AND business_id=%s AND action_type='day_brief' AND entity_type='operator_colleague' AND (%s OR user_id=%s)", (item_id, business, owner, user))
            action = _row(cursor, cursor.fetchone())
            if not action:
                raise PermissionError('Планёрка недоступна в выбранном бизнесе.')
            day = action['payload_json']['date']
    day = work_journal.local_day(cursor, business, day)
    people = members(cursor, business) if owner else []
    rows = assignments(cursor, business, user, owner=owner, day=day)
    return {'date': day, 'user_id': user, 'can_complete': actor['role'] != 'viewer', 'can_manage': owner, 'delivery_enabled': delivery_enabled(),
        'draft': (draft(cursor, business, user, day=day) or None) if owner else None,
        'members': [{'id': str(row['id']), 'name': row['name'],
            'platforms': [p for p, connected in [('telegram', row.get('telegram_id')), ('max', row.get('max_id') and row.get('notifications_enabled'))] if connected]} for row in people],
        'assignments': rows, 'deliveries':delivery_states(cursor,business,rows)}


def focus_request(message):
    """Extract an owner's stated focus, never infer tasks or recipients."""
    clean = str(message or '').strip()
    prefix = re.match(r'^фокус(?:\s+дня|\s+на\s+день)\b\s*[:—-]?\s*', clean, re.I)
    brief = re.match(r'^(?:подготовь\s+)?план[её]рк[ау](?:\s+на\s+(завтра|сегодня|\d{4}-\d{2}-\d{2}))?\s*[:—-]\s*(?:фокус\s*[:—-]\s*)?', clean, re.I)
    match = prefix or brief
    if not match:
        return '', None
    focus = clean[match.end():].lstrip(' \t\r\n:.,—-')
    focus = re.split(r'[.!\n]\s*(?:(?:пока\s+)?не\s+(?:публикуй|отправляй)|подготовь\s+(?:предварительный|черновик)|сотрудникам\s+ничего)', focus, maxsplit=1, flags=re.I)[0]
    return focus.strip(), brief.group(1).lower() if brief and brief.group(1) else None


def relevant_request(message, active=False):
    clean = str(message or '')
    if re.search(r'фокус\s+(?:дня|на день)|план[её]рк|мои задачи дня|статус задач|подготовь передачу задач', clean, re.I):
        return True
    if not active:
        return False
    if re.match(r'Сотрудники(?:\s+(?:MAX|Telegram))?\s*:|Задача для\s+\d+\s*:', clean, re.I):
        return True
    from services.operator_context import PlannerContext
    domains = PlannerContext(clean).domains
    return not domains or ('work' in domains and not domains.intersection({'finance', 'content', 'partnerships', 'integrations'}))


def route(cursor, *, business, user, message, channel, pending=None, conversation_id=None):
    if not operator_workday.enabled(business):
        return None
    pending = pending or {}
    clean = str(message or '').strip()
    active = pending.get('selected_day_brief') or pending.get('day_brief_employee') or pending.get('day_brief_members')
    if not relevant_request(clean, active=bool(active)):
        return None
    platform = 'max' if channel.startswith('max') else 'telegram'
    actor = authorize(cursor, business, user)
    if clean.casefold() in {'отмена', 'стоп', '/cancel'}:
        if conversation_id:
            cursor.execute("UPDATE operatoractions SET status='rejected',updated_at=NOW() WHERE (conversation_id=%s OR envelope_json->>'record_id'=%s) AND user_id=%s AND business_id=%s AND capability='work.day_brief' AND status IN ('pending','pending_approval')", (conversation_id, (pending.get('selected_day_brief') or {}).get('id') or (pending.get('selected_day_brief') or {}).get('item_id'), user, business))
        return {'status': 'cancelled', 'capability': 'work.day_brief', 'chat_response': 'Обсуждение закрыто. Неподтверждённая передача отменена. Черновики и уже переданные задачи сохранены.'}, {}
    if pending.get('day_brief_employee') or re.search('мои задачи дня', clean, re.I) or actor['role'] != 'owner':
        match = re.fullmatch(r'Выполнено:\s*(\d+)', clean, re.I)
        if match:
            indexed = pending.get('day_brief_employee') or []
            n = int(match[1]) - 1
            if not 0 <= n < len(indexed):
                raise ValueError('Откройте актуальные задачи дня и укажите номер.')
            complete_task(cursor, business=business, user=user, **indexed[n], done=True)
        rows = assignments(cursor, business, user, day=work_journal.local_day(cursor, business))
        indexed, lines = [], ['Ваши задачи дня:']
        for row in rows:
            for task in row['payload_json']['tasks']:
                indexed.append({'action_id': str(row['id']), 'task_id': task['id'], 'version': row['version']})
                lines.append(str(len(indexed)) + '. ' + ('✓ ' if task['done'] else '') + task['text'] + ' · ' + row['payload_json']['date'])
            lines.extend([item['wording'] for item in row['payload_json']['tips']])
            lines.append(row['payload_json']['note'])
        lines.append('Напишите «Выполнено: 1» или откройте планёрку, чтобы отметить задачу.' if indexed else 'Подтверждённых задач пока нет. Они появятся после проверки владельцем.')
        from services.operator_work_handoff import mobile_work_url
        return {'status': 'completed', 'capability': 'work.day_brief', 'chat_response': '\n\n'.join(lines),
            'work_return_url': mobile_work_url(business, str(rows[0]['id']) if rows else None, platform, 'work_journal', 'day_brief')}, {'day_brief_employee': indexed}
    selected = pending.get('selected_day_brief') or {}
    current = draft(cursor, business, user, identifier=selected.get('id') or selected['item_id']) if selected.get('id') or selected.get('item_id') else draft(cursor, business, user, day=work_journal.local_day(cursor, business))
    people = members(cursor, business)
    focus_text, requested_day = focus_request(clean)
    if focus_text:
        target_day = current.get('date')
        if requested_day:
            today = work_journal.local_day(cursor, business)
            target_day = (date.fromisoformat(today) + timedelta(days=1)).isoformat() if requested_day == 'завтра' else today if requested_day == 'сегодня' else requested_day
            current = draft(cursor, business, user, day=target_day)
        current = save(cursor, business=business, user=user, channel=channel, payload={'focus': focus_text,
            'date': target_day, 'recipients': current.get('recipients', []), 'version': current.get('version', 0), 'request_id': str(uuid.uuid4())})
    if re.search(r'статус задач', clean, re.I):
        rows = assignments(cursor, business, user, owner=True, day=current.get('date') or work_journal.local_day(cursor, business))
        lines = ['Выполнение задач команды:']
        for row in rows:
            person = next((p for p in people if str(p['id']) == row['user_id']), {'name': 'Доступ отозван'})
            lines.append(person['name'] + ': ' + '; '.join(('✓ ' if task['done'] else 'В работе: ') + task['text'] for task in row['payload_json']['tasks']))
        for delivery in delivery_states(cursor,business,rows):
            assignee=next(row['user_id'] for row in rows if str(row['id'])==delivery['action_id'])
            person=next((p for p in people if str(p['id'])==assignee),{'name':'Сотрудник'})
            lines.append(person['name']+' · '+('MAX' if delivery['platform']=='max' else 'Telegram')+': '+delivery_label(delivery['state']))
        from services.operator_work_handoff import mobile_work_url
        return {'status': 'completed', 'capability': 'work.day_brief', 'chat_response': '\n\n'.join(lines) if rows else 'Подтверждённых задач пока нет.',
            'work_return_url': mobile_work_url(business, current.get('id'), platform, 'work_journal', 'day_brief')}, pending
    chosen = re.fullmatch(r'Сотрудники(?:\s+(MAX|Telegram))?\s*:\s*([\d,\s]+)', clean, re.I)
    if chosen:
        if not current:
            raise ValueError('Сначала надиктуйте «Фокус дня: …».')
        previous_people = pending.get('day_brief_members') or []
        if not previous_people:
            raise ValueError('Откройте «Планёрка дня», чтобы получить список сотрудников.')
        ids = []
        for n in re.findall(r'\d+', chosen[2]):
            if not 1 <= int(n) <= len(previous_people):
                raise ValueError('Проверьте номера сотрудников.')
            ids.append(previous_people[int(n) - 1])
        destination = chosen[1].lower() if chosen[1] else platform
        targets = [{'user_id': uid, 'platforms': [destination], 'tasks': next((r['tasks'] for r in current['recipients'] if r['user_id'] == uid), [{'text': current['focus']}])} for uid in ids]
        current = save(cursor, business=business, user=user, channel=channel, payload={**current, 'recipients': targets, 'request_id': str(uuid.uuid4())})
    task = re.fullmatch(r'Задача для\s+(\d+)\s*:\s*(.+)', clean, re.I | re.S)
    if task:
        previous_people = pending.get('day_brief_members') or []
        if not current or not 1 <= int(task[1]) <= len(previous_people):
            raise ValueError('Откройте планёрку и проверьте номер сотрудника.')
        target = next((r for r in current['recipients'] if r['user_id'] == previous_people[int(task[1]) - 1]), None)
        if not target:
            raise ValueError('Сначала выберите этого сотрудника среди получателей.')
        target['tasks'].append({'text': task[2]})
        current = save(cursor, business=business, user=user, channel=channel, payload={**current, 'request_id': str(uuid.uuid4())})
    context = {'day_brief_members': [str(person['id']) for person in people]}
    if current:
        context['selected_day_brief'] = {'id': current['id'], 'version': current['version']}
    if re.search(r'подготовь передачу задач|передай задачи|отправь план[её]рку', clean, re.I):
        if not current:
            raise ValueError('Сначала сохраните фокус дня и выберите сотрудников.')
        prepared = prepare(cursor, business=business, user=user, identifier=current['id'], version=current['version'])
        from services.operator_work_handoff import mobile_work_url
        prepared['work_return_url'] = mobile_work_url(business, current['id'], platform, 'work_journal', 'day_brief')
        return prepared, context
    lines = ['Планёрка дня: надиктуйте «Фокус дня: …», выберите сотрудников, проверьте задачи и подсказки перед передачей.']
    if current:
        lines.extend(['Фокус: ' + current['focus'], 'Статус: ' + ('задачи переданы в кабинеты' if current['status'] == 'assigned' else 'черновик')])
        for target in current['recipients']:
            person = next((p for p in people if str(p['id']) == target['user_id']), {'name': 'Доступ отозван'})
            lines.append(person['name'] + ': ' + '; '.join(t['text'] for t in target['tasks']))
    lines.append('Сотрудники:')
    lines.extend(str(i + 1) + '. ' + str(person['name']) for i, person in enumerate(people))
    lines.append('«Сотрудники: 1, 2» — выбрать; «Сотрудники MAX: 1» — через MAX. «Задача для 1: …» — добавить задачу. «Подготовь передачу задач» — проверить перед подтверждением.')
    from services.operator_work_handoff import mobile_work_url
    result = {'status': 'completed', 'capability': 'work.day_brief', 'chat_response': '\n\n'.join(lines),
        'work_return_url': mobile_work_url(business, current.get('id'), platform, 'work_journal', 'day_brief')}
    return result, context


def chat_result(value):
    # A long team preview must never fail transport or expose an approval button
    # beside an incomplete preview. The same exact review remains in the miniapp.
    if len((value.get('chat_response') or '').encode('utf-16-le')) // 2 <= 3000:
        return value
    return {**{key: item for key, item in value.items() if key != 'approval'}, 'status': 'completed',
        'chat_response': 'Планёрка содержит большой список задач. Откройте планёрку кнопкой ниже: там показан полный текст каждому сотруднику и отдельное подтверждение передачи. Ничего не отправлено этим запросом.'}
