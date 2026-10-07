"""Reviewed day snapshots for the shared Operator. Never creates CRM bookings."""
import json
import os
import re
import uuid
from datetime import date, datetime, time, timedelta

from services.operator_conversations import _row
from services import work_journal, work_recommendations


def enabled(business_id):
    return business_id in {v.strip() for v in os.getenv('OPERATOR_WORKDAY_BUSINESS_IDS', '').split(',') if v.strip()}


def authorize(cursor, business_id, user_id, owner=False):
    if not enabled(business_id):
        raise PermissionError('Рабочие функции пока не включены для этого бизнеса.')
    return work_journal.scope(cursor, business_id, user_id, write=True, owner_only=owner)


def result(message, status='completed', **extra):
    return {'status': status, 'chat_response': message, 'capability': 'work.schedule', **extra}


def schedule(cursor, business_id, day):
    cursor.execute('SELECT * FROM operator_day_schedules WHERE business_id=%s AND day=%s', (business_id, day))
    return _row(cursor, cursor.fetchone())


def normalize_entries(entries, services):
    if not isinstance(entries, list) or len(entries) > 100:
        raise ValueError('Передайте не более 100 записей дня.')
    clean = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Проверьте строки расписания.')
        when = str(entry.get('time') or '')
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', when):
            raise ValueError('Уточните время каждой записи в формате ЧЧ:ММ.')
        service = work_recommendations.resolve_service(services, entry.get('service_id'), entry.get('service_name'))
        master = str(entry.get('master') or '').strip()
        if len(master) > 100:
            raise ValueError('Слишком длинное имя мастера.')
        duration = entry.get('duration_minutes')
        if duration is not None and (type(duration) is not int or not 1 <= duration <= 1440):
            raise ValueError('Длительность — целое число минут; неизвестную оставьте пустой.')
        key = (when, service['id'], master)
        if key in seen:
            raise ValueError('В расписании повторяется время, услуга и мастер. Уточните записи.')
        seen.add(key)
        clean.append({'time': when, 'service_id': service['id'], 'service_name': service['name'],
                      'master': master, 'duration_minutes': duration})
    return sorted(clean, key=lambda e: (e['time'], e['master'], e['service_name']))


def prepare(cursor, business_id, user_id, args, source):
    authorize(cursor, business_id, user_id)
    message = str(source.get('message') or '')
    if re.search(r'не\s+(?:сохраняй|записывай|вноси)', message, re.I):
        raise ValueError('Расписание не сохраняется: вы попросили не вносить данные.')
    if args.get('entries') == [] and not re.search(r'очист|удал|пуст|нет запис|отмен.*все', message, re.I):
        raise ValueError('Подтвердите, что расписание дня пустое.')
    day = work_journal.local_day(cursor, business_id, args.get('date'))
    current = schedule(cursor, business_id, day)
    if args.get('version') != current.get('version', 0):
        raise ValueError('Расписание изменилось. Сначала прочитайте актуальный день.')
    entries = normalize_entries(args.get('entries'), work_recommendations.catalog(cursor, business_id))
    envelope = {'day': day, 'version': current.get('version', 0), 'entries': entries,
                'source': source, 'business_id': business_id}
    lines = [f"Расписание на {day}: {len(entries)} записей."]
    if current:
        lines.append('После подтверждения заменит текущий снимок дня; предыдущая версия сохранится.')
    lines.extend(f"{e['time']} · {e['service_name']} · {e['master'] or 'мастер не указан'} · "
                 + (f"{e['duration_minutes']} мин." if e['duration_minutes'] else 'длительность неизвестна') for e in entries)
    lines.append('Подтвердите расписание для планёрки.')
    text = '\n'.join(lines)
    return result(text, 'approval_required', approval={'summary': text, 'envelope': envelope})


def apply(cursor, business_id, user_id, envelope, action_id):
    authorize(cursor, business_id, user_id)
    if envelope.get('business_id') != business_id:
        raise PermissionError('Чужое расписание.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('schedule:'+business_id+':'+envelope['day'],))
    cursor.execute('SELECT after_json FROM operator_schedule_history WHERE action_id=%s AND business_id=%s', (action_id, business_id))
    old = _row(cursor, cursor.fetchone())
    if old:
        return result('Расписание уже сохранено.', schedule=old['after_json'], idempotent=True)
    before = schedule(cursor, business_id, envelope['day'])
    if before.get('version', 0) != envelope['version']:
        return result('Расписание изменилось после проверки. Подготовьте обновление заново.', 'blocked')
    entries = normalize_entries(envelope['entries'], work_recommendations.catalog(cursor, business_id))
    cursor.execute('''INSERT INTO operator_day_schedules(id,business_id,day,entries_json,source_json,updated_by)
        VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s)
        ON CONFLICT(business_id,day) DO UPDATE SET entries_json=EXCLUDED.entries_json,
        source_json=EXCLUDED.source_json,version=operator_day_schedules.version+1,
        updated_by=EXCLUDED.updated_by,updated_at=NOW() RETURNING *''',
        (str(uuid.uuid4()), business_id, envelope['day'], json.dumps(entries, ensure_ascii=False),
         json.dumps(envelope['source'], ensure_ascii=False), user_id))
    after = _row(cursor, cursor.fetchone())
    cursor.execute('''INSERT INTO operator_schedule_history(action_id,schedule_id,business_id,version,before_json,after_json)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb)''',
        (action_id, after['id'], business_id, after['version'], json.dumps(before, default=str), json.dumps(after, default=str)))
    return result('Расписание сохранено. Можно провести планёрку.', schedule=after)


def free_minutes(entry, entries):
    """Only a known end and the next visit for the same master establish a gap."""
    if not entry.get('master') or not entry.get('duration_minutes'):
        return None
    start = datetime.combine(date(2000, 1, 1), time.fromisoformat(entry['time']))
    following = [datetime.combine(start.date(), time.fromisoformat(e['time'])) for e in entries
                 if e.get('master') == entry['master'] and e['time'] > entry['time']]
    if not following:
        return None
    return max(0, (min(following) - start - timedelta(minutes=entry['duration_minutes'])).total_seconds() // 60)


def briefing(cursor, business_id, user_id, args):
    authorize(cursor, business_id, user_id)
    day = work_journal.local_day(cursor, business_id, args.get('date'))
    current = schedule(cursor, business_id, day)
    if not current:
        return result('Расписание на этот день пока не проверено. Пришлите его голосом, файлом или фотографией.', 'clarification_required')
    services = work_recommendations.catalog(cursor, business_id)
    policy = work_recommendations.policy(cursor, business_id)
    matrix = policy.get('matrix_json')
    if matrix is None:
        matrix = work_recommendations.matrix(cursor, business_id).get('matrix_json')
    entries = current['entries_json']
    items = []
    lines = [f'Планёрка на {day}. Записей: {len(entries)}.']
    if not matrix:
        lines.append('Связки допродаж ещё не настроены. Владелец может проверить их в разделе «Средний чек».')
    for entry in entries:
        # Imported master names are not master IDs: never bypass master-specific rules.
        cursor.execute('SELECT id FROM masters WHERE business_id=%s AND name=%s', (business_id, entry['master']))
        matches = [_row(cursor, r) for r in cursor.fetchall()]
        master_id = matches[0]['id'] if len(matches) == 1 else None
        rules = policy.get('rules_json') or []
        unresolved_rules = master_id is None and any(r.get('master_id') for r in rules)
        from zoneinfo import ZoneInfo
        from services.finance_daily import settings
        timezone = settings(cursor, business_id).get('timezone')
        if not timezone:
            raise ValueError('Укажите часовой пояс бизнеса для проверки правил дня.')
        moment = datetime.combine(date.fromisoformat(day), time.fromisoformat(entry['time']), ZoneInfo(timezone))
        addons = [] if unresolved_rules else work_recommendations.select(services, matrix, rules, entry['service_id'],
                    master_id, free_minutes(entry, entries), now=moment)
        items.append({**entry, 'recommendations': addons})
        lines.append(f"\n{entry['time']} · {entry['service_name']} · {entry['master'] or 'мастер не указан'}")
        if unresolved_rules:
            lines.append('Уточните мастера для применения его правил рекомендаций.')
        for addon in addons:
            lines.append(f"• {addon['service_name']}, {addon.get('price') or 'цена не указана'}. {addon['reason']}")
            lines.append(addon.get('admin_script') or addon.get('master_script') or 'Формулировка предложения не настроена.')
            if not addon['time_verified']:
                lines.append('Нужно проверить свободное время.')
    return result('\n'.join(lines), items=items, schedule_version=current['version'], date=day)


def tools(cursor, business_id, user_id, message, source):
    def context(args):
        authorize(cursor, business_id, user_id)
        day = work_journal.local_day(cursor, business_id, args.get('date'))
        current = schedule(cursor, business_id, day)
        query = str(args.get('service_query') or '').casefold()
        services = work_recommendations.catalog(cursor, business_id)
        selected = [s for s in services if query in s['name'].casefold()]
        return result('Расписание и услуги для планёрки.', date=day, version=current.get('version', 0),
                      entries=current.get('entries_json', []), services=[{k:s.get(k) for k in ('id','name','price')} for s in selected[:40]],
                      services_has_more=len(selected)>40)
    text = {'type':'string'}
    definitions = [
        {'name':'work.day_context','description':'Перед сохранением расписания прочитай версию дня и услуги. Ищи service_query; отсутствие в первых 40 не означает отсутствие услуги.',
         'input_schema':{'type':'object','properties':{'date':text,'service_query':text}},'execute':context},
        {'name':'work.prepare_schedule','description':'Подготовить полное расписание на проверку, без создания CRM записей. Передай все строки дня, version из day_context. Не выдумывай время, мастеров, услуги и длительность. Если число или строка не читается, уточни. Для исправления прочитай полный текущий день. Пустой список только по явной команде очистить расписание.',
         'input_schema':{'type':'object','required':['date','version','entries'],'properties':{'date':text,'version':{'type':'integer'},
            'entries':{'type':'array','items':{'type':'object','required':['time','service_name'],'properties':{'time':text,'service_name':text,'service_id':text,'master':text,'duration_minutes':{'type':['integer','null']}}}}}},
         'prepare_approval':lambda a:prepare(cursor,business_id,user_id,a,source),'approval_required':True},
        {'name':'work.morning_briefing','description':'Провести утреннюю планёрку по проверенному снимку расписания и действующим связкам допродаж. Отправка коллегам — отдельное действие.',
         'input_schema':{'type':'object','properties':{'date':text}},'execute':lambda a:briefing(cursor,business_id,user_id,a),'deterministic_response':True},
    ]
    for tool in definitions:
        tool.update(capability='work.schedule', title='Планёрка и расписание', risk_class='internal_write' if tool.get('approval_required') else 'read_only')
    return definitions
