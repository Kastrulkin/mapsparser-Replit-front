"""Dated capacity and staff facts in the existing reversible work journal."""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from services import work_journal, operator_workday, finance_daily
from services.operator_conversations import _row


def matches(message):
    return bool(re.search(r'кресл|рабоч.{0,8}мест|доступност|загрузк|мастер.{0,70}(?:отсутств|забол|не вый|не работа)|(?:план|что.{0,15}делать).{0,40}(?:сегодня|дальше|дня)|рабоч.{0,15}(?:сведен|факт)', message, re.I))


def read_request(cursor,business_id,user_id,message):
    plan_request=bool(re.match(r'\s*(?:что(?:\s+мне)?\s+делать|дай\s+(?:конкретный\s+)?план|покажи\s+план\s+дня)',message,re.I))
    facts_request=bool(re.match(r'\s*(?:покажи|прочитай|выведи|сколько|какие)',message,re.I) and re.search(r'кресл|рабоч.{0,20}(?:сведен|факт)|отсутств',message,re.I))
    if not plan_request and not facts_request:return None
    explicit=re.search(r'\b\d{4}-\d{2}-\d{2}\b',message)
    day=explicit.group() if explicit else 'yesterday' if re.search(r'\bвчера\b',message,re.I) else 'today'
    if not explicit and re.search(r'\bзавтра\b',message,re.I):
        day=(date.fromisoformat(work_journal.local_day(cursor,business_id))+timedelta(days=1)).isoformat()
    return plan(cursor,business_id,user_id,{'date':day}) if plan_request else facts_result(cursor,business_id,user_id,{'date':day})


def validate(cursor, business_id, data, quote):
    if not isinstance(data, dict) or data.get('kind') not in {'capacity','absence'}:
        raise ValueError('Укажите доступность рабочих мест или отсутствие мастера.')
    day=work_journal.local_day(cursor,business_id,data.get('date'))
    clean={'kind':data['kind'],'date':day}
    if data['kind']=='capacity':
        count=data.get('count')
        if type(count) is not int or not 0 <= count <= 1000:
            raise ValueError('Укажите число свободных рабочих мест от 0 до 1000.')
        words={0:'ноль',1:'одно|один|одна',2:'два|две',3:'три',4:'четыре',5:'пять',6:'шесть',7:'семь',8:'восемь',9:'девять',10:'десять'}
        count_pattern=r'(?<!\d)'+str(count)+r'(?!\d)|\b(?:'+words.get(count,'(?!)')+r')\b'
        if not re.search(count_pattern,quote,re.I):
            raise ValueError('Число мест должно быть явно указано в сообщении.')
        for key in ('start','end'):
            value=str(data.get(key) or '')
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value) or value not in quote:
                raise ValueError('Укажите начало и конец доступности в формате ЧЧ:ММ.')
            clean[key]=value
        if clean['end']<=clean['start']:
            raise ValueError('Конец интервала должен быть позже начала в тот же день.')
        clean['count']=count
    else:
        master=str(data.get('master') or '').strip()
        if not master or len(master)>100 or master.casefold() not in quote.casefold():
            raise ValueError('Укажите имя отсутствующего мастера в сообщении.')
        if not re.search(r'отсутств|забол|не (?:вый|работа)|недоступ',quote,re.I):
            raise ValueError('Укажите отсутствие мастера явно.')
        clean['master']=master
    # Retain operational availability, not a diagnosis or inferred medical detail.
    return clean


def read(cursor,business_id,user_id,day):
    actor=work_journal.scope(cursor,business_id,user_id)
    if not actor['all_visits']:
        raise PermissionError('Рабочую доступность всей точки читает владелец или администратор.')
    cursor.execute("""SELECT id,version,facts_json,created_at FROM business_work_journal
        WHERE business_id=%s AND NOT is_voided AND facts_json->'operational'->>'date'=%s
        ORDER BY created_at,id LIMIT 501""",(business_id,day))
    rows=[_row(cursor,row) for row in cursor.fetchall()]
    if len(rows)>500:raise ValueError('Слишком много фактов дня. Уточните период.')
    return rows


def describe(row):
    fact=row['facts_json']['operational']
    if fact['kind']=='capacity':return f"{fact['start']}–{fact['end']}: свободных рабочих мест — {fact['count']}."
    return 'Отсутствует мастер: '+fact['master']+'.'


def facts_result(cursor,business_id,user_id,args):
    day=work_journal.local_day(cursor,business_id,args.get('date'))
    rows=read(cursor,business_id,user_id,day)
    return operator_workday.result('Рабочие факты на '+day+':\n'+('\n'.join(describe(row) for row in rows) or 'Данных о доступности и отсутствии мастеров пока нет.'),
        day_facts=rows,date=day)


def plan(cursor,business_id,user_id,args):
    operator_workday.authorize(cursor,business_id,user_id)
    day=work_journal.local_day(cursor,business_id,args.get('date'))
    rows=read(cursor,business_id,user_id,day)
    snapshot=operator_workday.schedule(cursor,business_id,day)
    absent={row['facts_json']['operational']['master'].casefold() for row in rows if row['facts_json']['operational']['kind']=='absence'}
    entries=snapshot.get('entries_json') or []
    conflicts=[entry for entry in entries if entry.get('master','').casefold() in absent]
    lines=['План дня на '+day+'.','Сохранённые рабочие факты:']
    from services.operator_owner_actions import effective_hours
    hours=effective_hours(cursor,business_id,day)
    if hours:
        lines.append('Временные часы работы: '+hours['time']+'–'+hours['end']+' ('+hours['timezone']+'). В другие дни действует постоянный график.')
    lines.extend(describe(row) for row in rows)
    if not rows:lines.append('Доступность рабочих мест и отсутствие мастеров не указаны.')
    lines.append('Записей в проверенном расписании: '+str(len(entries))+'.' if snapshot else 'Проверенного расписания на этот день пока нет.')
    report=None
    if finance_daily.enabled(business_id):
        finance_daily.authorize(cursor,business_id,user_id)
        report=finance_daily.read_period(cursor,business_id,day,day)
        for currency,values in report['currencies'].items():
            lines.append(f"{currency}: выручка {values.get('revenue')}, чеки {values.get('checks')}, средний чек {values.get('average_check')}.")
    lines.append('Следующие действия:')
    if absent:
        lines.append('1. Исключите отсутствующих мастеров из доступного состава на этот день. Автоматических переносов и назначений нет.')
    if conflicts:
        lines.append('Проверьте статус и необходимость переноса записей отсутствующих мастеров: '+ '; '.join(e['time']+' · '+e['service_name']+' · '+e['master'] for e in conflicts)+'. Согласуйте с клиентами и доступными сотрудниками.')
    capacities=[row['facts_json']['operational'] for row in rows if row['facts_json']['operational']['kind']=='capacity']
    zone=finance_daily.settings(cursor,business_id).get('timezone')
    now=datetime.now(ZoneInfo(zone)) if zone else None
    for capacity in capacities:
        past=now is not None and (date.fromisoformat(day)<now.date() or (date.fromisoformat(day)==now.date() and capacity['end']<=now.strftime('%H:%M')))
        if past:
            lines.append(f"Окно {capacity['start']}–{capacity['end']} уже завершилось; не предлагайте запись в прошедшее время.")
        elif capacity['count']:
            lines.append(f"В {capacity['start']}–{capacity['end']} доступны {capacity['count']} рабочих места. До предложения записи проверьте присутствующего мастера и длительность услуги: свободное кресло не означает свободного сотрудника.")
    if not snapshot:lines.append('Добавьте полное расписание дня, чтобы проверить конфликты и длительность свободных окон.')
    elif not capacities:lines.append('Укажите доступность рабочих мест и время работы присутствующих мастеров; свободные часы не выдуманы.')
    lines.append('Ничего не опубликовано, клиенты и сотрудники не уведомлены, записи не перенесены.')
    return operator_workday.result('\n'.join(lines),date=day,day_facts=rows,financial_daily=report,schedule_version=snapshot.get('version'),schedule_conflicts=conflicts)


def tools(cursor,business_id,user_id,channel,message,request_key):
    def save(args):
        actor=work_journal.scope(cursor,business_id,user_id,True)
        if not actor['all_visits']:raise PermissionError('Доступность всей точки изменяет владелец или администратор.')
        if re.search(r'не\s+(?:сохраняй|записывай|вноси)',message,re.I):raise ValueError('Вы попросили не сохранять сведения.')
        if re.match(r'\s*(?:что|как|почему|покажи|прочитай|сколько|если|например|допустим)\b',message,re.I):raise ValueError('Вопрос или пример не сохраняется как рабочий факт.')
        if args.get('id'):
            row=work_journal.read_entry(cursor,business_id,actor,args['id'])
            if not row.get('facts_json',{}).get('operational'):raise ValueError('Это не рабочий факт дня.')
        if not args.get('void'):
            args={**args,'operational':validate(cursor,business_id,args.get('operational'),str(args.get('quote') or ''))}
            fact=args['operational']
            for existing in read(cursor,business_id,user_id,fact['date']):
                previous=existing['facts_json']['operational']
                if existing['id']==args.get('id'):continue
                if previous==fact:
                    return operator_workday.result('Этот рабочий факт уже сохранён:\n'+describe(existing),day_facts=[existing],idempotent=True)
                if previous['kind']==fact['kind']=='capacity' and fact['start']<previous['end'] and previous['start']<fact['end']:
                    raise ValueError('Интервал пересекается с сохранённой доступностью. Укажите id/version существующего факта для исправления.')
        row=work_journal.save_note(cursor,business_id,user_id,channel,None,
            request_key+':day-fact:'+work_journal.digest(args),message,{**args,'category':'operations','outcome':'note'})
        return operator_workday.result('Рабочий факт отменён.' if row['is_voided'] else 'Сохранил рабочий факт на '+row['facts_json']['operational']['date']+':\n'+describe(row),
            day_facts=[row],result_ref={'href':'/dashboard/work-journal?business_id='+business_id+'&entry='+row['id'],'label':'Открыть рабочий факт'})
    text={'type':'string'}
    operational={'type':'object','required':['kind','date'],'properties':{'kind':{'type':'string','enum':['capacity','absence']},'date':text,'count':{'type':'integer'},'start':text,'end':text,'master':text}}
    return [
        {'name':'work.save_day_fact','title':'Доступность и отсутствие мастеров','capability':'work.journal','risk_class':'internal_observation_write',
         'description':'Сохранить фактическую доступность кресел/рабочих мест (capacity: count,start,end) или отсутствие мастера (absence: master) на конкретный день. Это рабочие факты, не заметки контента, не CRM-перенос и не диагноз. date=today/yesterday или точная дата. quote — точный фрагмент сообщения, не вопрос и не пример. Для исправления/отмены нужны id/version из read_day_facts; void=true отменяет. Не придумывай число, время и имя; уточняй недостающие поля. При конфликте интервалов предложи исправить существующий факт.',
         'input_schema':{'type':'object','properties':{'quote':text,'operational':operational,'id':text,'version':{'type':'integer'},'void':{'type':'boolean'}}},'execute':save,'deterministic_response':True},
        {'name':'work.read_day_facts','title':'Прочитать рабочую доступность','capability':'work.schedule','risk_class':'read_only',
         'description':'Прочитать сохранённые факты доступности рабочих мест и отсутствия мастеров за date, включая id/version для исправления. Не используй историю чата вместо базы.',
         'input_schema':{'type':'object','properties':{'date':text}},'execute':lambda a:facts_result(cursor,business_id,user_id,a),'deterministic_response':True},
        {'name':'work.day_plan','title':'Что делать сегодня','capability':'work.schedule','risk_class':'read_only',
         'description':'Дать план следующих действий по сохранённым рабочим фактам дня, проверенному расписанию и дневным финансовым итогам. Выявляет записи отсутствующих мастеров. Ничего не переносит и не отправляет.',
         'input_schema':{'type':'object','properties':{'date':text}},'execute':lambda a:plan(cursor,business_id,user_id,a),'deterministic_response':True},
    ]
