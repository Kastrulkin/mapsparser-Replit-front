"""Scoped work facts. Notes never post revenue or change owner policy."""
import hashlib
import logging
import json
import os
import re
import uuid
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from services.operator_conversations import _row


def enabled(business_id):
    return business_id in {v.strip() for v in os.getenv('OPERATOR_WORK_JOURNAL_BUSINESS_IDS','').split(',') if v.strip()}


def installed(cursor):
    cursor.execute("SELECT to_regclass('business_work_journal') present")
    return bool(_row(cursor,cursor.fetchone()).get('present'))


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()


def scope(cursor,business_id,user_id,write=False,owner_only=False):
    from services.operator_audio import authorize_actor
    actor,_=authorize_actor(cursor,user_id,business_id)
    if write and not enabled(business_id):raise PermissionError('Новый рабочий журнал пока отключён для этого бизнеса.')
    owner=actor.get('role')=='business_owner' or bool(actor.get('is_superadmin'))
    role='owner' if owner else 'viewer'
    if not owner:
        cursor.execute("SELECT role FROM business_members WHERE business_id=%s AND user_id=%s AND status='active'",(business_id,user_id))
        membership=_row(cursor,cursor.fetchone())
        if not membership:raise PermissionError('Доступ сотрудника к бизнесу отозван.')
        role=membership.get('role') or 'viewer'
    if owner_only and not owner:raise PermissionError('Правила и привязки сотрудников изменяет владелец бизнеса.')
    if write and role not in {'owner','manager','member'}:raise PermissionError('Нет права вносить рабочие сведения.')
    cursor.execute('SELECT master_id FROM business_master_bindings WHERE business_id=%s AND user_id=%s',(business_id,user_id))
    master_id=_row(cursor,cursor.fetchone()).get('master_id')
    return {'user_id':user_id,'role':role,'all_visits':role in {'owner','manager'},'master_id':master_id}


def local_day(cursor,business_id,value=None):
    if value and value not in {'today','yesterday','сегодня','вчера'}:return date.fromisoformat(str(value)).isoformat()
    from services.finance_daily import settings
    config=settings(cursor,business_id)
    if not config.get('timezone'):raise ValueError('Укажите точную дату или сохраните часовой пояс бизнеса.')
    today=datetime.now(ZoneInfo(config['timezone'])).date()
    return (today-timedelta(days=1 if value in {'yesterday','вчера'} else 0)).isoformat()


def booking(cursor,business_id,actor,booking_id):
    cursor.execute('SELECT to_jsonb(b) data FROM bookings b WHERE id=%s AND business_id=%s',(booking_id,business_id))
    row=_row(cursor,cursor.fetchone()).get('data') or {}
    if not row or (not actor['all_visits'] and (not actor['master_id'] or str(row.get('master_id'))!=str(actor['master_id']))):
        raise PermissionError('Запись не найдена среди доступных вам визитов.')
    return row


def visit_time(cursor,business_id,row):
    from services.finance_daily import settings
    zone=settings(cursor,business_id).get('timezone')
    local=row.get('booking_time_local')
    value=row.get('booking_time')
    if local:
        # Existing provider writes local timestamp followed by a zone abbreviation.
        raw=str(local).strip().replace(' ', 'T', 1)
        raw=re.sub(r' [A-Za-z]{2,6}$','',raw)
    elif row.get('booking_date') and value and len(str(value))<=15:
        raw=str(row['booking_date'])+'T'+str(value)
    else:raw=str(value or '')
    try:parsed=datetime.fromisoformat(raw.replace('Z','+00:00'))
    except ValueError:return None
    if not parsed.tzinfo:
        if not zone:return None
        parsed=parsed.replace(tzinfo=ZoneInfo(zone))
    return parsed.astimezone(ZoneInfo(zone)) if zone else parsed


def list_bookings(cursor,business_id,actor,target_date):
    if not actor['all_visits'] and not actor['master_id']:return []
    cursor.execute("SELECT to_regclass('bookings') present")
    if not _row(cursor,cursor.fetchone()).get('present'):return []
    # Date fields differ between legacy and provider bookings. Scope before fetching,
    # then interpret timestamps in the business zone, never the server zone.
    cursor.execute("""SELECT to_jsonb(b) data FROM bookings b WHERE business_id=%s
        AND (%s OR to_jsonb(b)->>'master_id'=%s)
        AND (COALESCE(to_jsonb(b)->>'booking_date','')=%s
          OR left(COALESCE(to_jsonb(b)->>'booking_time_local',''),10)=%s
          OR left(COALESCE(to_jsonb(b)->>'booking_time',''),10) BETWEEN %s AND %s)
        ORDER BY COALESCE(to_jsonb(b)->>'booking_time_local',to_jsonb(b)->>'booking_time',to_jsonb(b)->>'id') LIMIT 501""",
        (business_id,actor['all_visits'],actor['master_id'],target_date,target_date,
         (date.fromisoformat(target_date)-timedelta(days=1)).isoformat(),(date.fromisoformat(target_date)+timedelta(days=1)).isoformat()))
    rows=[_row(cursor,r)['data'] for r in cursor.fetchall()]
    if len(rows)>500:raise ValueError('Слишком много визитов. Уточните запись или услугу.')
    result=[]
    for row in rows:
        when=visit_time(cursor,business_id,row)
        day=when.date().isoformat() if when else str(row.get('booking_date') or '')
        if day==target_date and row.get('status') not in {'cancelled','canceled','rejected'}:result.append(row)
    return result


def read_entry(cursor,business_id,actor,entry_id):
    cursor.execute('SELECT * FROM business_work_journal WHERE id=%s AND business_id=%s',(entry_id,business_id))
    row=_row(cursor,cursor.fetchone())
    if not row:raise PermissionError('Запись журнала не найдена.')
    if not actor['all_visits'] and row['user_id']!=actor['user_id']:
        if not row.get('booking_id'):raise PermissionError('Нет доступа к записи журнала.')
        booking(cursor,business_id,actor,row['booking_id'])
    return row


def list_entries(cursor,business_id,user_id,query='',target_date=None):
    actor=scope(cursor,business_id,user_id)
    params=[business_id]
    access=''
    if not actor['all_visits']:
        access=' AND user_id=%s';params.append(user_id)
        if actor['master_id']:
            access=' AND (user_id=%s OR booking_id IN (SELECT id FROM bookings WHERE business_id=j.business_id AND master_id=%s))';params.append(actor['master_id'])
    params.append('%'+str(query or '')[:200]+'%')
    clause=''
    if target_date:
        day=local_day(cursor,business_id,target_date)
        from services.finance_daily import settings
        zone=settings(cursor,business_id).get('timezone')
        if not zone:raise ValueError('Для фильтра по местному дню сохраните часовой пояс бизнеса.')
        clause=' AND (j.occurred_at AT TIME ZONE %s)::date=%s';params.extend([zone,day])
    cursor.execute('SELECT j.* FROM business_work_journal j WHERE business_id=%s'+access+" AND COALESCE(facts_json->>'quote',original_text) ILIKE %s"+clause+' ORDER BY occurred_at DESC,id DESC LIMIT 100',tuple(params))
    return [_row(cursor,row) for row in cursor.fetchall()]


def history(cursor,business_id,user_id,entry_id):
    actor=scope(cursor,business_id,user_id);read_entry(cursor,business_id,actor,entry_id)
    cursor.execute("SELECT * FROM business_work_history WHERE business_id=%s AND target_id=%s AND kind='note' ORDER BY created_at DESC LIMIT 100",(business_id,entry_id))
    return [_row(cursor,row) for row in cursor.fetchall()]


def _audit(cursor,business_id,user_id,channel,kind,target_id,request_key,before,after):
    cursor.execute('''INSERT INTO business_work_history(id,business_id,user_id,channel,kind,target_id,request_key,before_json,after_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)''',(str(uuid.uuid4()),business_id,user_id,channel,kind,target_id,request_key,json.dumps(before,default=str),json.dumps(after,default=str)))


def save_note(cursor,business_id,user_id,channel,message_id,request_key,original,args):
    actor=scope(cursor,business_id,user_id,True)
    if not request_key or len(request_key)>250:raise ValueError('Нужен идентификатор записи.')
    if not isinstance(args,dict):raise ValueError('Нужны параметры наблюдения.')
    request_key=user_id+':'+request_key
    request_hash=digest([original,args])
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('work-journal:'+business_id,))
    actor=scope(cursor,business_id,user_id,True)
    cursor.execute('SELECT after_json FROM business_work_history WHERE business_id=%s AND request_key=%s',(business_id,request_key))
    replay=_row(cursor,cursor.fetchone())
    if replay:
        if replay['after_json'].get('request_hash')!=request_hash:raise ValueError('Идентификатор запроса уже использован для другого изменения.')
        read_entry(cursor,business_id,actor,replay['after_json']['id'])
        logging.getLogger(__name__).info('work_journal_event status=duplicate')
        return replay['after_json']
    entry_id=args.get('id');before=read_entry(cursor,business_id,actor,entry_id) if entry_id else {}
    if before and before['user_id']!=user_id and actor['role']!='owner':raise PermissionError('Исправлять запись может её автор или владелец.')
    if before and args.get('version')!=before['version']:raise ValueError('Запись уже изменена. Откройте её заново.')
    quote=str(args.get('quote') or '').strip()
    if not args.get('void'):
        normalize=lambda value:' '.join(str(value).casefold().replace('ё','е').split())
        if not quote or len(quote)>6000 or normalize(quote) not in normalize(original):raise ValueError('Нужно точное сообщение сотрудника, без придуманных фактов.')
        if re.match(r'\s*(?:если|например|допустим|что если|может ли|как |почему |что )',quote,re.I) or quote.endswith('?'):
            raise ValueError('Вопрос или предположение не сохраняется как произошедшее событие.')
    elif not before:raise ValueError('Укажите запись для отмены.')
    facts=dict(before.get('facts_json') or {})
    if quote and quote!=facts.get('quote') and before and 'outcome' not in args:
        facts.update(outcome='note',reason=None,addon_service_id=None)
    for key in ('outcome','reason','addon_service_id'):
        if key in args:facts[key]=args[key]
    if quote:facts['quote']=quote
    outcome=facts.get('outcome')
    if outcome not in {None,'note','offered','declined','interested','performed'}:raise ValueError('Неизвестный результат предложения.')
    reason=facts.get('reason')
    if 'reason' in args and reason and (len(str(reason))>1000 or str(reason).casefold() not in original.casefold()):raise ValueError('Причину нужно взять из сообщения сотрудника.')
    booking_id=args.get('booking_id',before.get('booking_id'));service_id=args.get('service_id',before.get('service_id'))
    visit=booking(cursor,business_id,actor,booking_id) if booking_id else {}
    for service in [service_id,facts.get('addon_service_id')]:
        if service:
            cursor.execute('SELECT id FROM userservices WHERE id=%s AND business_id=%s',(service,business_id))
            if not cursor.fetchone():raise ValueError('Услуга не найдена в выбранном бизнесе.')
    task_id=args.get('task_id',before.get('task_id'))
    if task_id:
        cursor.execute('SELECT user_id FROM operator_async_jobs WHERE id=%s AND business_id=%s',(task_id,business_id))
        task=_row(cursor,cursor.fetchone())
        if not task or (task.get('user_id')!=user_id and actor['role']!='owner'):raise PermissionError('Нет доступа к этой задаче.')
    occurred=args.get('occurred_at') or before.get('occurred_at') or datetime.now(timezone.utc)
    if isinstance(occurred,str):occurred=datetime.fromisoformat(occurred.replace('Z','+00:00'))
    if not occurred.tzinfo:raise ValueError('Укажите время с часовым поясом.')
    event_date=event_day(cursor,business_id,occurred) if booking_id and outcome in {'offered','declined','interested','performed'} and not args.get('void') else None
    entry_id=entry_id or str(uuid.uuid4())
    cursor.execute('''INSERT INTO business_work_journal(id,business_id,user_id,channel,message_id,request_key,original_text,facts_json,booking_id,service_id,task_id,occurred_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
        ON CONFLICT(id) DO UPDATE SET facts_json=EXCLUDED.facts_json,booking_id=EXCLUDED.booking_id,service_id=EXCLUDED.service_id,task_id=EXCLUDED.task_id,
            occurred_at=EXCLUDED.occurred_at,version=business_work_journal.version+1,is_voided=%s,updated_at=NOW() RETURNING *''',
        (entry_id,business_id,user_id,channel,message_id,request_key,original,json.dumps(facts),booking_id,service_id,task_id,occurred,bool(args.get('void'))))
    after=_row(cursor,cursor.fetchone());after['request_hash']=request_hash
    after['change_source']={'message_id':message_id,'channel':channel,'user_id':user_id,'text':original}
    # Unlinked observations do not become attributed visit results.
    cursor.execute('UPDATE averageticketevents SET is_voided=TRUE WHERE journal_id=%s',(entry_id,))
    if booking_id and outcome in {'offered','declined','interested','performed'} and not after['is_voided']:
        cursor.execute('''INSERT INTO averageticketevents(id,business_id,journal_id,booking_id,main_service_id,addon_service_id,event_type,event_date,master_id,notes,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(journal_id) WHERE journal_id IS NOT NULL DO UPDATE SET booking_id=EXCLUDED.booking_id,main_service_id=EXCLUDED.main_service_id,
                addon_service_id=EXCLUDED.addon_service_id,event_type=EXCLUDED.event_type,event_date=EXCLUDED.event_date,master_id=EXCLUDED.master_id,notes=EXCLUDED.notes,is_voided=FALSE''',
            (str(uuid.uuid4()),business_id,entry_id,booking_id,service_id or visit.get('service_id'),facts.get('addon_service_id'),outcome,event_date,visit.get('master_id'),reason,user_id))
    _audit(cursor,business_id,user_id,channel,'note',entry_id,request_key,before,after)
    logging.getLogger(__name__).info('work_journal_event status=%s channel=%s','cancelled' if after['is_voided'] else 'corrected' if before else 'saved',channel)
    return after


def event_day(cursor,business_id,occurred):
    from services.finance_daily import settings
    zone=settings(cursor,business_id).get('timezone')
    if not zone:raise ValueError('Для результата визита сохраните часовой пояс бизнеса.')
    return occurred.astimezone(ZoneInfo(zone)).date()
