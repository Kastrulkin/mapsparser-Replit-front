"""Narrow finance planning tools; all writes use an approved orchestrator action."""
import re
import sys
from datetime import date, timedelta
from services import finance_daily
from services.operator_conversations import _row


def finance_input(message):
    if re.search(r'пост|контент|новост|услуг.*(?:добав|созда)',message,re.I):
        return False
    return bool(re.search(r'выруч|продаж|чек|доп(?:а|ов|родаж)|расход|возврат|финанс|доход|часов.*пояс|валют',message,re.I))


def observation(text,status='completed',**extra):
    return {'status':status,'chat_response':text,'result_ref':{'href':'/dashboard/finance','label':'Открыть финансы'},'external_writes_performed':False,**extra}


def context(cursor,business_id,user_id,args):
    finance_daily.authorize(cursor,business_id,user_id)
    current=finance_daily.day_context(cursor,business_id)
    day=args.get('date') or current.get('today')
    if day in {'today','yesterday','сегодня','вчера'}:
        day=(date.fromisoformat(current['today'])-timedelta(days=1 if day in {'yesterday','вчера'} else 0)).isoformat() if current.get('today') else None
    report=finance_daily.read_period(cursor,business_id,day,day) if day else None
    cursor.execute('SELECT id,name FROM userservices WHERE business_id=%s AND COALESCE(is_active,TRUE)=TRUE ORDER BY name LIMIT 300',(business_id,))
    services=[_row(cursor,row) for row in cursor.fetchall()]
    return observation('Текущие финансовые данные.',settings=current,report=report,services=services)


def read(cursor,business_id,user_id,args):
    finance_daily.authorize(cursor,business_id,user_id)
    current=finance_daily.day_context(cursor,business_id)
    start=args.get('start') or current.get('today')
    end=args.get('end') or start
    if not start:
        return observation('Укажите дату или сохраните часовой пояс бизнеса.','clarification_required')
    report=finance_daily.read_period(cursor,business_id,start,end)
    lines=[f'Финансы за {start} — {end}.']
    for currency,values in report['currencies'].items():
        labels={'revenue':'Выручка до возвратов','refunds':'Возвраты','net_revenue':'После возвратов','checks':'Чеки','upsell_checks':'Чеки с допом','average_check':'Средний чек','upsell_share':'Доля чеков с допом, %','expenses':'Расходы'}
        lines.append(currency+': '+ '; '.join(label+': '+(str(values.get(key)) if values.get(key) is not None else 'неизвестно') for key,label in labels.items()))
    if not report['days']:lines.append('За этот период дневных данных нет.')
    if any(day['reconciliation_status']=='needs_review' for day in report['days']):lines.append('Есть расхождения с детализацией. Подтверждённый итог сохранён; суммы не сложены повторно.')
    if report['period_aggregates']:lines.append('Есть агрегаты за несколько дней: они не распределены по дням и требуют сверки.')
    return observation('\n'.join(lines),financial_daily=report)


def tools(cursor,business_id,user_id,message,channel,message_ref,orchestrator=None,previous_draft=None):
    def prepare(arguments):
        if re.search(r'\bне\s+(?:сохраня|вноси|записыва|добавля)',message,re.I) or re.match(r'\s*(?:если|например|допустим)',message,re.I):
            return observation('Финансовые данные не записаны. Для записи дайте явную команду.','clarification_required')
        try:
            arguments=dict(arguments)
            if previous_draft and arguments.get('date') in {None,'','today','сегодня'} and previous_draft.get('date'):
                arguments['date']=previous_draft['date']
            envelope=finance_daily.prepare(cursor,business_id,user_id,arguments,channel,message_ref)
        except (ValueError,PermissionError):
            return observation(str(sys.exception()),'clarification_required')
        from services.operator_core import _prepare_registered_capability_approval
        outcome=_prepare_registered_capability_approval(capability='finance.daily.write',tool_name='finance.prepare_facts',business_id=business_id,
            user_id=user_id,channel=channel,message=message+"\n"+finance_daily.fingerprint(envelope),payload=envelope,backend_capability='finance.daily.apply_operator',orchestrator=orchestrator)
        if outcome.get('status')=='approval_required':
            cursor.execute('SELECT name FROM businesses WHERE id=%s',(business_id,))
            business=_row(cursor,cursor.fetchone())
            outcome['chat_response']=(business.get('name') or 'Выбранный бизнес')+'\n'+finance_daily.preview_text(envelope)
            outcome['financial_draft']=envelope
            outcome['approval']['summary']=outcome['chat_response']
        return outcome
    money={'type':['string','number','null']}
    entries=[
        {'name':'finance.daily_context','capability':'finance.read','title':'Настройки и данные дня','description':'Перед финансовой записью прочитай часовой пояс, валюту, реальные услуги и существующие итоги. Не придумывай часовой пояс, валюту и текущую дату. Относительные даты передавай как today/yesterday; вычислит сервер.',
         'input_schema':{'type':'object','properties':{'date':{'type':'string'}}},'risk_class':'read_only','execute':lambda a:context(cursor,business_id,user_id,a)},
        {'name':'finance.read_days','capability':'finance.read','title':'Финансовые итоги и сверка','description':'Показать общие финансовые данные за точные даты, не складывая сводку и операции повторно.',
         'input_schema':{'type':'object','properties':{'start':{'type':'string'},'end':{'type':'string'}}},'risk_class':'read_only','deterministic_response':True,'execute':lambda a:read(cursor,business_id,user_id,a)},
        {'name':'finance.prepare_facts','capability':'finance.daily.write','title':'Подготовить финансовую запись',
         'description':'Готовит одно подтверждение, НЕ записывает данные. kind=daily для итога/количества продаж: не выдумывай отдельные продажи. 10 продаж и 2 допа = checks 10, upsell_checks 2, допы включены в revenue. revenue до возвратов; refunds отдельно. Неизвестное пропускай, не подставляй ноль. mode=set заменяет переданные поля, add увеличивает известные, void отменяет сводку или конкретную transaction_id. При исправлении preview используй первоначальную дату. kind=transaction для одной конкретной продажи/расхода/возврата. receipt_id только из реальной связанной операции, иначе пропусти. kind=settings только по явному согласию сохранить валюту/часовой пояс. Валюта ISO, timezone IANA. services — только произнесённые названия, без распределения общей суммы. Суммы и числа извлекай строго из сообщения. Если пользователь сообщает выручку ПОСЛЕ возвратов, прибавь явно указанный возврат для revenue и покажи обе суммы. Не делай операций на основе примеров или вопросов.',
         'input_schema':{'type':'object','required':['kind'],'properties':{'kind':{'type':'string','enum':['daily','transaction','settings']},'mode':{'type':'string','enum':['set','add','void']},
            'date':{'type':'string'},'currency':{'type':'string'},'timezone':{'type':'string'},'values':{'type':'object','properties':{**{key:money for key in finance_daily.FIELDS},'notes':{'type':'string'},'services':{'type':'array','items':{'type':'string'}}}},
            'transaction_id':{'type':'string'},'transaction_type':{'type':'string','enum':['income','expense','refund']},'amount':money,'notes':{'type':'string'},'receipt_id':{'type':'string'},
            'sale_type':{'type':'string','enum':['service','upsell','cross_sell']},'has_upsell':{'type':'boolean'}}},
         'risk_class':'financial_write_request','approval_required':True,'deterministic_preparation_response':True,'prepare_approval':prepare}]
    for entry in entries:
        if 'execute' in entry:
            handler=entry['execute']
            def invoke(args,handler=handler):
                try:return handler(args)
                except (ValueError,PermissionError):return observation(str(sys.exception()),'clarification_required')
            entry['execute']=invoke
    return entries
