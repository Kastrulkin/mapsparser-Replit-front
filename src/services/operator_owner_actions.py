"""Owner tasks and dated hours on the existing journey-action approval boundary."""
import hashlib
import json
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.business_permissions import load_actor, require_permission
from services.business_input_settings import resolve
from services.operator_conversations import _row


ENTITY = {'task': 'owner_task', 'reminder': 'owner_reminder', 'hours': 'business_hours_override'}
MONTHS = ('января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря')


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def authorize(cursor,business,user,kind='task'):
    from services.operator_workday import enabled
    if not enabled(business):
        raise PermissionError('Управление рабочим днём пока не включено для этого бизнеса.')
    actor=load_actor(cursor,user)
    require_permission(cursor,business,actor,'business.settings.write' if kind=='hours' else 'operations.write')
    return actor


def result(text,status='completed',**extra):
    return {'status':status,'capability':'work.owner_action','chat_response':text,
            'external_writes_performed':False,**extra}


def source_dates(message,zone):
    days=set(re.findall(r'\b\d{4}-\d{2}-\d{2}\b',message))
    for match in re.finditer(r'\b(\d{1,2})\s+('+'|'.join(MONTHS)+r')\s+(20\d{2})\b',message,re.I):
        days.add(date(int(match[3]),MONTHS.index(match[2].lower())+1,int(match[1])).isoformat())
    local=now().astimezone(ZoneInfo(zone)).date()
    for word,offset in (('сегодня',0),('завтра',1),('послезавтра',2)):
        if re.search(r'\b'+word+r'\b',message,re.I):days.add((local+timedelta(days=offset)).isoformat())
    return days


def normalize(cursor,business,args,message):
    kind=args.get('kind')
    if kind not in ENTITY:raise ValueError('Выберите задачу, напоминание или временные часы работы.')
    if re.match(r'\s*(?:если|например|допустим|можно ли|что если)\b',message,re.I):
        raise ValueError('Пример не создаёт задачу. Дайте явное поручение.')
    quote=str(args.get('quote') or '').strip()
    normalized=lambda value:' '.join(value.casefold().split())
    if not quote or normalized(quote) not in normalized(message):raise ValueError('Нужна точная цитата поручения.')
    settings=resolve(cursor,business)
    zone=str(args.get('timezone') or settings.get('timezone') or '')
    if not zone:raise ValueError('Укажите часовой пояс напоминания или бизнеса.')
    ZoneInfo(zone)
    aliases={'Europe/Moscow':r'москв','Asia/Dubai':r'дуба'}
    if zone != settings.get('timezone') and zone not in message and not re.search(aliases.get(zone,r'(?!)'),message,re.I):
        raise ValueError('Уточните часовой пояс, отличный от настроек бизнеса.')
    day=str(args.get('date') or '')
    if day not in source_dates(message,zone):raise ValueError('Укажите точную дату и год или «завтра».')
    date.fromisoformat(day)
    start=str(args.get('time') or '')
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',start) or start not in message:
        raise ValueError('Укажите время в формате ЧЧ:ММ.')
    due=datetime.fromisoformat(day+'T'+start).replace(tzinfo=ZoneInfo(zone))
    # Local times in a DST gap or repeated hour require a precise offset.
    if due.astimezone(timezone.utc).astimezone(ZoneInfo(zone)).replace(tzinfo=None)!=due.replace(tzinfo=None) or due.utcoffset()!=due.replace(fold=1).utcoffset():
        raise ValueError('Это время неоднозначно из-за перевода часов. Выберите другое время.')
    if due<=now():raise ValueError('Указанное время уже прошло. Выберите будущую дату и время.')
    title=str(args.get('title') or {'task':'Задача владельца','reminder':'Напоминание владельцу','hours':'Временные часы работы'}[kind]).strip()
    text=str(args.get('text') or quote).strip()
    if not 1<=len(title)<=160 or not 1<=len(text)<=3000:raise ValueError('Сократите название или текст задачи.')
    data={'kind':kind,'date':day,'time':start,'timezone':zone,'due_at':due.isoformat(),'title':title,'text':text,'quote':quote}
    if kind=='hours':
        end=str(args.get('end') or '')
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',end) or end not in message or end<=start:
            raise ValueError('Укажите время закрытия после времени открытия.')
        data.update(end=end,delivery='in_app')
    else:
        delivery=args.get('delivery') or 'in_app'
        if delivery not in {'in_app','telegram'}:raise ValueError('Выберите «Сегодня» или свой подключённый Telegram.')
        if delivery=='telegram' and not re.search(r'телеграм|telegram',message,re.I):
            raise ValueError('Для доставки в Telegram явно укажите этот канал.')
        data['delivery']=delivery
    return data


def telegram_target(cursor,user):
    cursor.execute('SELECT telegram_id FROM telegramcontrolpreferences WHERE user_id=%s',(user,))
    target=str(_row(cursor,cursor.fetchone()).get('telegram_id') or '').strip()
    if not target:raise ValueError('Сначала подключите свой Telegram к LocalOS. Можно сохранить напоминание в «Сегодня».')
    return target


def permanent_hours(cursor,business):
    cursor.execute('SELECT working_hours FROM businesses WHERE id=%s',(business,))
    return _row(cursor,cursor.fetchone()).get('working_hours')


def read(cursor,business,user,args):
    authorize(cursor,business,user)
    cursor.execute('''SELECT id,version,status,title,description,due_at,payload_json FROM journey_actions
        WHERE business_id=%s AND (user_id=%s OR entity_type='business_hours_override')
          AND entity_type=ANY(%s) AND status NOT IN ('cancelled','superseded')
        ORDER BY due_at,id LIMIT 50''',(business,user,list(ENTITY.values())))
    items=[_row(cursor,r) for r in cursor.fetchall()]
    if args.get('date'):items=[r for r in items if r['payload_json'].get('date')==args['date']]
    lines=[]
    for row in items:
        data=row['payload_json']
        time_label=data['time']+('–'+data['end'] if data.get('end') else '')
        delivery='Telegram' if data.get('delivery')=='telegram' else 'Сегодня в LocalOS'
        lines.append(f"{row['title']} — {data['date']} {time_label} ({data['timezone']}), {row['status']}; {delivery}; id {row['id']}, версия {row['version']}")
    return result('\n'.join(lines) or 'Сохранённых задач, напоминаний и временных часов нет.',owner_actions=items,
        result_ref={'href':'/dashboard/today?business_id='+business,'label':'Открыть задачи'})


def prepare(cursor,business,user,args,message):
    if args.get('operation')=='cancel':
        authorize(cursor,business,user)
        cursor.execute('SELECT * FROM journey_actions WHERE id=%s AND business_id=%s AND user_id=%s AND entity_type=ANY(%s)',
            (args.get('id'),business,user,list(ENTITY.values())))
        row=_row(cursor,cursor.fetchone())
        if not row or row.get('version')!=args.get('version'):raise ValueError('Задача изменилась. Сначала прочитайте её актуальную версию.')
        authorize(cursor,business,user,(row.get('payload_json') or {}).get('kind','task'))
        envelope={'operation':'cancel','business_id':business,'user_id':user,'id':str(row['id']),'version':row['version']}
        text='Отменить «'+row['title']+'»?'
    else:
        authorize(cursor,business,user,args.get('kind','task'))
        data=normalize(cursor,business,args,message)
        authorize(cursor,business,user,data['kind'])
        if data['delivery']=='telegram':data['telegram_id']=telegram_target(cursor,user)
        envelope={'operation':'create','business_id':business,'user_id':user,'data':data}
        if data['kind']=='hours':
            envelope['permanent_hours_version']=digest(permanent_hours(cursor,business))
            text=f"Только {data['date']}: {data['time']}–{data['end']} ({data['timezone']}). Постоянный график сохранится; в остальные дни действует он."
        else:
            channel='раздел «Сегодня» в LocalOS' if data['delivery']=='in_app' else 'ваш подключённый Telegram'
            text=f"{data['title']}\n{data['text']}\n{data['date']} в {data['time']} ({data['timezone']})\nДоставка: {channel}."
        text+='\nПодтвердите сохранение. До подтверждения ничего не создано.'
    envelope['fingerprint']=digest(envelope)
    return result(text,'approval_required',approval={'summary':text,'capability':'work.owner_action','envelope':envelope})


def session_write_guard(session):
    if (session or {}).get('session_kind') == 'demo' or (session or {}).get('impersonating') or (session or {}).get('impersonated_by'):
        raise PermissionError('В этой сессии изменения недоступны. Войдите в свой аккаунт.')


def apply(cursor,business,user,envelope,action_id,session=None):
    session_write_guard(session)
    if envelope.get('business_id')!=business or envelope.get('user_id')!=user:raise PermissionError('Неверная область задачи.')
    unsigned={k:v for k,v in envelope.items() if k!='fingerprint'}
    if digest(unsigned)!=envelope.get('fingerprint'):raise ValueError('Условия подтверждения изменились.')
    if envelope['operation']=='cancel':
        authorize(cursor,business,user)
        cursor.execute('SELECT * FROM journey_actions WHERE id=%s AND business_id=%s AND user_id=%s FOR UPDATE',(envelope['id'],business,user))
        row=_row(cursor,cursor.fetchone())
        if not row:raise PermissionError('Задача недоступна.')
        authorize(cursor,business,user,(row.get('payload_json') or {}).get('kind','task'))
        if row['status']=='cancelled':return result('Задача уже отменена.',idempotent=True)
        if row['version']!=envelope['version']:raise ValueError('Задача изменилась. Подготовьте отмену снова.')
        cursor.execute("UPDATE journey_actions SET status='cancelled',version=version+1,updated_at=NOW() WHERE id=%s",(row['id'],))
        return result('Задача отменена. Отложенная доставка остановлена.')
    data=envelope['data']
    authorize(cursor,business,user,data['kind'])
    identifier=str(uuid.uuid5(uuid.NAMESPACE_URL,'owner-action:'+business+':'+user+':'+digest(data)))
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('owner-action:'+business+':'+data['date'],))
    cursor.execute('SELECT id,status FROM journey_actions WHERE id=%s AND business_id=%s',(identifier,business))
    existing=_row(cursor,cursor.fetchone())
    if existing:return result('Это поручение уже сохранено. Статус: '+existing['status']+'.',owner_action_id=identifier,idempotent=True)
    if datetime.fromisoformat(data['due_at'])<=now():raise ValueError('Время прошло. Подготовьте новое подтверждение.')
    if data['delivery']=='telegram' and telegram_target(cursor,user)!=data['telegram_id']:raise ValueError('Telegram изменился. Подготовьте подтверждение заново.')
    if data['kind']=='hours':
        if digest(permanent_hours(cursor,business))!=envelope['permanent_hours_version']:raise ValueError('Постоянный график изменился. Подготовьте подтверждение заново.')
        cursor.execute("SELECT id FROM journey_actions WHERE business_id=%s AND entity_type='business_hours_override' AND status='ready' AND payload_json->>'date'=%s FOR UPDATE",(business,data['date']))
        if cursor.fetchone():raise ValueError('На этот день уже есть временный график. Прочитайте и отмените его перед заменой.')
    cursor.execute('''INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,entity_id,action_type,status,
        title,description,cta_label,cta_target_json,payload_json,dedupe_key,due_at)
        VALUES (%s,%s,%s,'work_journal',%s,%s,'owner_action','ready',%s,%s,'Открыть задачу',%s::jsonb,%s::jsonb,%s,%s)''',
        (identifier,business,user,ENTITY[data['kind']],identifier,data['title'],data['text'],
         json.dumps({'href':'/dashboard/operator','business_id':business}),json.dumps(data,ensure_ascii=False),'owner-action:'+identifier,data['due_at']))
    text='Временные часы сохранены только на '+data['date']+'. Постоянный график не изменён.' if data['kind']=='hours' else 'Поручение сохранено на '+data['date']+' '+data['time']+' ('+data['timezone']+').'
    if data['delivery']=='telegram':text+=' Доставка запланирована; сообщение ещё не отправлено.'
    else:text+=' Результат доступен в «Сегодня» и через чтение задач в чате.'
    return result(text,owner_action_id=identifier,result_ref={'href':'/dashboard/today?business_id='+business,'entity_id':identifier,'label':'Открыть задачи'})


def today_items(cursor,scope,user):
    if scope.get('kind') not in {'business','network'}:
        return []
    cursor.execute("SELECT to_regclass('journey_actions') present")
    if not _row(cursor,cursor.fetchone()).get('present'):
        return []
    identifiers=list(scope.get('business_ids') or [])
    if scope.get('kind')=='business':
        identifiers=[scope['id']]
    # Include the network's own parent profile, then recheck access per item.
    cursor.execute("SELECT a.id,a.business_id,a.title,a.description,a.status,a.due_at,a.updated_at,a.payload_json,b.name business_name FROM journey_actions a JOIN businesses b ON b.id=a.business_id WHERE (a.business_id=ANY(%s) OR (%s='network' AND b.network_id=%s)) AND a.user_id=%s AND a.entity_type=ANY(%s) AND a.status IN ('ready','waiting','in_progress') ORDER BY a.due_at,a.id LIMIT 50",
        (identifiers,scope['kind'],scope['id'],user,list(ENTITY.values())))
    rows=[_row(cursor,row) for row in cursor.fetchall()]
    items=[]
    for row in rows:
        try:
            authorize(cursor,row['business_id'],user,(row['payload_json'] or {}).get('kind','task'))
        except PermissionError:
            continue
        data=row['payload_json'];time_label=data['time']+('–'+data['end'] if data.get('end') else '')
        items.append({'id':'owner-action:'+str(row['id']),'kind':'owner_action','entity_id':str(row['id']),
            'title':row['title'],'description':row['description'],
            'stage':data['date']+' '+time_label+' ('+data['timezone']+')',
            'status':row['status'],'due_at':row['due_at'].isoformat(),'occurred_at':row['updated_at'].isoformat(),
            'business_id':row['business_id'],'business_name':row['business_name'],'screen':'operator'})
    return items


def effective_hours(cursor,business,day):
    cursor.execute("SELECT to_regclass('journey_actions') present")
    if not _row(cursor,cursor.fetchone()).get('present'):return None
    cursor.execute("SELECT payload_json FROM journey_actions WHERE business_id=%s AND entity_type='business_hours_override' AND status='ready' AND payload_json->>'date'=%s ORDER BY created_at DESC LIMIT 1",(business,day))
    return _row(cursor,cursor.fetchone()).get('payload_json')


def tools(cursor,business,user,message,session=None):
    text={'type':'string'}
    def preview(args):
        try:
            session_write_guard(session)
            return prepare(cursor,business,user,args,message)
        except PermissionError:return result(str(sys.exception()),'blocked')
        except (ValueError,ZoneInfoNotFoundError):return result(str(sys.exception()),'clarification_required')
    return [
        {'name':'work.prepare_owner_action','capability':'work.owner_action','title':'Задача, напоминание или часы на один день',
         'description':'Подготовить подтверждение задачи с дедлайном, разового напоминания владельцу или временного графика на один день. kind task/reminder/hours. Дата ISO, time ЧЧ:ММ, timezone IANA; quote точный текст поручения. Для hours end — закрытие. delivery in_app (раздел Сегодня, без push) или telegram только по явному выбору собственного подключённого Telegram. Не отправляет клиентам, не меняет постоянный график. Повторяющиеся сводки создавай через agents.create. operation=cancel требует id/version из read_owner_actions.',
         'input_schema':{'type':'object','properties':{**{key:text for key in ('kind','date','time','end','timezone','quote','title','text','delivery','id','operation')},'version':{'type':'integer'}}},
         'risk_class':'internal_write','approval_required':True,'deterministic_preparation_response':True,'prepare_approval':preview},
        {'name':'work.read_owner_actions','capability':'work.owner_action','title':'Прочитать задачи и напоминания',
         'description':'Читает сохранённые задачи, напоминания и временный график выбранного бизнеса; date опционально. Показывает id/version для отмены.',
         'input_schema':{'type':'object','properties':{'date':text}},'risk_class':'read_only','deterministic_response':True,
         'execute':lambda args:read(cursor,business,user,args)},
    ]
