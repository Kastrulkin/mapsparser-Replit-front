"""Daily finance facts and reconciled totals shared by chat and dashboards."""
import hashlib
import json
import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from services.operator_conversations import _row

MONEY = ('revenue','refunds','expenses')
COUNTS = ('checks','upsell_checks')
FIELDS = MONEY + COUNTS


def enabled(business_id):
    return business_id in {value.strip() for value in os.getenv('OPERATOR_FINANCE_INPUT_BUSINESS_IDS','').split(',') if value.strip()}


def installed(cursor):
    cursor.execute("SELECT to_regclass('finance_daily_summaries') present")
    return bool(_row(cursor,cursor.fetchone()).get('present'))


def authorize(cursor,business_id,user_id,write=False):
    from services.operator_audio import authorize_actor
    actor,access=authorize_actor(cursor,user_id,business_id)
    from subscription_manager import capability_access_payload
    if not capability_access_payload(access,'finance').get('allowed'):
        raise PermissionError('Финансы недоступны на текущем тарифе.')
    if write:
        if not enabled(business_id):
            raise PermissionError('Новый финансовый ввод пока недоступен для этого бизнеса.')
        if actor.get('role')!='business_owner' and not actor.get('is_superadmin'):
            cursor.execute("SELECT role FROM business_members WHERE business_id=%s AND user_id=%s AND status='active'",(business_id,user_id))
            if _row(cursor,cursor.fetchone()).get('role') not in {'manager','admin'}:
                raise PermissionError('Изменять финансы может владелец или управляющий бизнеса.')
    return actor,access


def settings(cursor,business_id):
    cursor.execute('SELECT * FROM business_finance_settings WHERE business_id=%s',(business_id,))
    return _row(cursor,cursor.fetchone()) or {'business_id':business_id,'version':0,'currency':None,'timezone':None}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()


def number(value,count=False):
    if value is None:
        return None
    if isinstance(value,bool):
        raise ValueError('Нужно число, а не логическое значение.')
    try:
        parsed=Decimal(str(value).replace(' ','').replace(',','.'))
    except InvalidOperation:
        raise ValueError('Не удалось прочитать сумму или количество.')
    if not parsed.is_finite() or parsed<0 or parsed>Decimal('99999999999.99') or parsed!=parsed.quantize(Decimal('1') if count else Decimal('.01')):
        raise ValueError('Сумма должна быть неотрицательной, с двумя десятичными знаками; количество — целым.')
    return str(parsed)


def checked_values(values):
    if not isinstance(values,dict) or set(values)-set(FIELDS)-{'notes','services'}:
        raise ValueError('Неизвестные поля дневного итога.')
    result={field:number(values[field],field in COUNTS) for field in FIELDS if field in values}
    if values.get('notes') is not None:
        if not isinstance(values['notes'],str) or len(values['notes'])>4000:
            raise ValueError('Пояснение должно быть текстом до 4000 символов.')
        result['notes']=values['notes']
    if 'services' in values:
        if not isinstance(values['services'],list) or len(values['services'])>50 or any(not isinstance(name,str) or len(name)>200 for name in values['services']):
            raise ValueError('Укажите до 50 названий услуг.')
        result['services']=values['services']
    if result.get('checks') is not None and result.get('upsell_checks') is not None and Decimal(result['upsell_checks'])>Decimal(result['checks']):
        raise ValueError('Чеков с допродажей не может быть больше общего количества чеков.')
    return result


def day_context(cursor,business_id):
    config=settings(cursor,business_id)
    today=datetime.now(ZoneInfo(config['timezone'])).date().isoformat() if config.get('timezone') else None
    return {**config,'today':today,'rules':'Чеки с допом входят в общее число чеков; допы включены в выручку. Выручка указана до возвратов.'}


def prepare(cursor,business_id,user_id,args,channel,message_ref):
    authorize(cursor,business_id,user_id,True)
    kind=args.get('kind','daily')
    config=settings(cursor,business_id)
    if kind=='transaction' and args.get('transaction_id'):
        cursor.execute('SELECT to_jsonb(t) data FROM financialtransactions t WHERE id=%s AND business_id=%s',(args['transaction_id'],business_id))
        original=_row(cursor,cursor.fetchone()).get('data') or {}
        if not original:raise ValueError('Операция не найдена в выбранном бизнесе.')
        args=dict(args)
        if not args.get('date'):args['date']=str(original['transaction_date'])[:10]
        if not args.get('currency'):args['currency']=original.get('currency')
    if kind=='settings':
        currency=(args.get('currency') or config.get('currency') or '').upper()
        zone=args.get('timezone') or config.get('timezone')
        if not re.fullmatch('[A-Z]{3}',currency):
            raise ValueError('Уточните валюту трёхбуквенным кодом, например EUR или RUB.')
        try:
            ZoneInfo(zone or '')
        except (ZoneInfoNotFoundError,ValueError):
            raise ValueError('Уточните часовой пояс бизнеса, например Europe/Tallinn.')
        return {'kind':kind,'before_version':config['version'],'data':{'currency':currency,'timezone':zone},'channel':channel,'message_ref':message_ref}
    if kind not in {'daily','transaction'}:
        raise ValueError('Неизвестный вид финансовой записи.')
    currency=(args.get('currency') or config.get('currency') or '').upper()
    if not re.fullmatch('[A-Z]{3}',currency):
        raise ValueError('Укажите валюту или сохраните её в настройках финансов.')
    target_date=args.get('date')
    if target_date in {'today','yesterday','сегодня','вчера',None,''}:
        if not config.get('timezone'):
            raise ValueError('Укажите точную дату или сохраните часовой пояс бизнеса.')
        from datetime import timedelta
        target_date=(datetime.now(ZoneInfo(config['timezone'])).date()-timedelta(days=1 if target_date in {'yesterday','вчера'} else 0)).isoformat()
    target_date=date.fromisoformat(target_date).isoformat()
    mode=args.get('mode','set')
    if mode not in {'set','add','void'}:
        raise ValueError('Выберите замену итога, дополнение или отмену записи.')
    if kind=='transaction':
        transaction_id=args.get('transaction_id')
        before={}
        if transaction_id:
            cursor.execute('SELECT to_jsonb(t) data FROM financialtransactions t WHERE id=%s AND business_id=%s',(transaction_id,business_id))
            before=_row(cursor,cursor.fetchone()).get('data') or {}
            if not before:
                raise ValueError('Операция не найдена в выбранном бизнесе.')
        elif mode=='void':
            raise ValueError('Уточните операцию для отмены.')
        transaction_type=args.get('transaction_type') or before.get('transaction_type')
        if transaction_type not in {'income','expense','refund'}:
            raise ValueError('Укажите доход, расход или возврат.')
        amount=number(args.get('amount',before.get('amount')))
        if mode!='void' and (amount is None or Decimal(amount)<=0):
            raise ValueError('Укажите положительную сумму операции.')
        if mode=='add' and before:
            if args.get('amount') is None:raise ValueError('Укажите сумму дополнения.')
            amount=number(str(Decimal(str(before['amount']))+Decimal(amount)))
        receipt_id=args.get('receipt_id') or before.get('receipt_id')
        if receipt_id:
            cursor.execute('SELECT id FROM financialtransactions WHERE id=%s AND business_id=%s AND NOT is_voided',(receipt_id,business_id))
            if not cursor.fetchone():raise ValueError('Связанный чек не найден в этом бизнесе.')
        sale_type=args.get('sale_type') or before.get('sale_type') or 'service'
        if sale_type not in {'service','upsell','cross_sell'}:raise ValueError('Неизвестный тип продажи.')
        if sale_type=='upsell' and not receipt_id:raise ValueError('Укажите чек, к которому относится допродажа, либо внесите общий дневной итог.')
        data={'amount':amount,'transaction_type':transaction_type,'transaction_date':target_date,'currency':currency,
              'description':(args.get('notes') or before.get('description') or '')[:4000],'receipt_id':receipt_id,
              'sale_type':sale_type,'has_upsell':args.get('has_upsell',before.get('has_upsell'))}
        return {'kind':kind,'target_id':transaction_id,'before_hash':fingerprint(before),'mode':mode,'data':data,'channel':channel,'message_ref':message_ref}
    cursor.execute('SELECT * FROM finance_daily_summaries WHERE business_id=%s AND date=%s AND currency=%s',(business_id,target_date,currency))
    existing=_row(cursor,cursor.fetchone())
    previous=existing.get('values_json') or {}
    if mode=='void' and (not existing or existing.get('is_voided')):
        raise ValueError('Активная сводка дня не найдена.')
    patch=checked_values(args.get('values') or {})
    if mode!='void' and not patch:
        raise ValueError('Укажите значения для сохранения.')
    if mode=='add':
        for field in FIELDS:
            if field in patch:
                if previous.get(field) is None or existing.get('is_voided'):
                    raise ValueError('Исходный итог неизвестен. Назовите полный итог: '+field)
                if patch[field] is None:
                    raise ValueError('Нельзя прибавить неизвестное значение.')
                patch[field]=str(Decimal(previous[field])+Decimal(patch[field]))
    values=checked_values({**({} if existing.get('is_voided') else previous),**patch})
    names=values.get('services') or []
    matched=[]
    for name in names:
        cursor.execute('SELECT id,name FROM userservices WHERE business_id=%s AND COALESCE(is_active,TRUE)=TRUE AND lower(name)=lower(%s)',(business_id,name))
        matches=[_row(cursor,row) for row in cursor.fetchall()]
        if len(matches)>1:
            raise ValueError('Несколько услуг с названием «'+name+'». Уточните название.')
        matched.append({'name':name,'service_id':matches[0]['id'] if matches else None})
    return {'kind':kind,'date':target_date,'currency':currency,'mode':mode,'before_version':existing.get('version',0),
            'data':values,'service_links':matched,'channel':channel,'message_ref':message_ref}


def preview_text(envelope):
    if envelope['kind']=='settings':
        return 'Сохранить настройки финансов: '+envelope['data']['currency']+', '+envelope['data']['timezone']+'?'
    if envelope['kind']=='transaction':
        data=envelope['data']
        return ('Отменить' if envelope['mode']=='void' else 'Сохранить')+f" операцию { {'income':'доход', 'expense':'расход', 'refund':'возврат'}[data['transaction_type']] } за {data['transaction_date']}: {data['amount']} {data['currency']}? {data['description']}"
    labels={'revenue':'Выручка до возвратов','refunds':'Возвраты','expenses':'Расходы','checks':'Всего чеков','upsell_checks':'Чеков с допродажей'}
    values=envelope['data']
    lines=[('Отменить сводку' if envelope['mode']=='void' else 'Сохранить итог')+f" за {envelope['date']} ({envelope['currency']})?"]
    lines.extend(labels[field]+': '+(str(values[field]) if values.get(field) is not None else 'не указано') for field in FIELDS)
    if values.get('revenue') is not None and values.get('refunds') is not None:
        lines.append('После возвратов: '+str(Decimal(values['revenue'])-Decimal(values['refunds'])))
    lines.append('Допы включены в выручку и общее число чеков. Отдельные операции повторно не прибавляются.')
    if values.get('notes'):lines.append(values['notes'])
    if values.get('services'):lines.append('Услуги без распределения выручки: '+', '.join(values['services']))
    return '\n'.join(lines)


def apply(cursor,business_id,user_id,envelope,action_id):
    authorize(cursor,business_id,user_id,True)
    if not action_id:raise ValueError('Отсутствует подтверждённое действие.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('finance-daily:'+business_id,))
    cursor.execute('SELECT after_json FROM finance_daily_events WHERE business_id=%s AND action_id=%s',(business_id,action_id))
    replay=_row(cursor,cursor.fetchone())
    if replay:return replay['after_json']
    kind=envelope['kind'];before={};data=envelope['data']
    if kind=='settings':
        if not re.fullmatch('[A-Z]{3}',data.get('currency') or ''):raise ValueError('Неверная валюта.')
        ZoneInfo(data.get('timezone') or '')
        before=settings(cursor,business_id)
        if before['version']!=envelope['before_version']:
            raise ValueError('Настройки изменились. Подготовьте новое подтверждение.')
        cursor.execute('''INSERT INTO business_finance_settings(business_id,currency,timezone) VALUES (%s,%s,%s)
            ON CONFLICT(business_id) DO UPDATE SET currency=EXCLUDED.currency,timezone=EXCLUDED.timezone,version=business_finance_settings.version+1,updated_at=NOW()''',(business_id,data['currency'],data['timezone']))
        target_id=business_id;after=settings(cursor,business_id)
    elif kind=='daily':
        cursor.execute('SELECT * FROM finance_daily_summaries WHERE business_id=%s AND date=%s AND currency=%s FOR UPDATE',(business_id,envelope['date'],envelope['currency']))
        before=_row(cursor,cursor.fetchone())
        if before.get('version',0)!=envelope['before_version']:
            raise ValueError('Итог дня изменился. Подготовьте новое подтверждение.')
        data=checked_values(data)
        target_id=before.get('id') or str(uuid.uuid4())
        cursor.execute('''INSERT INTO finance_daily_summaries(id,business_id,date,currency,values_json,is_voided,user_id,channel,message_ref)
            VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
            ON CONFLICT(business_id,date,currency) DO UPDATE SET values_json=EXCLUDED.values_json,is_voided=EXCLUDED.is_voided,
                version=finance_daily_summaries.version+1,user_id=EXCLUDED.user_id,channel=EXCLUDED.channel,message_ref=EXCLUDED.message_ref,updated_at=NOW()
            RETURNING *''',(target_id,business_id,envelope['date'],envelope['currency'],json.dumps(data),envelope['mode']=='void',user_id,envelope['channel'],envelope.get('message_ref')))
        after=_row(cursor,cursor.fetchone())
    elif kind=='transaction':
        number(data.get('amount'))
        if data.get('transaction_type') not in {'income','expense','refund'} or Decimal(data['amount'])<=0:
            raise ValueError('Неверная операция.')
        date.fromisoformat(data['transaction_date'])
        target_id=envelope.get('target_id') or str(uuid.uuid5(uuid.NAMESPACE_URL,'finance-operation:'+action_id))
        if data.get('receipt_id'):
            cursor.execute("SELECT id FROM financialtransactions WHERE id=%s AND business_id=%s AND NOT is_voided AND transaction_type='income' AND currency=%s AND transaction_date=%s FOR UPDATE",(data['receipt_id'],business_id,data['currency'],data['transaction_date']))
            if not cursor.fetchone():raise ValueError('Связанный чек изменился или недоступен. Подготовьте новое подтверждение.')
        if not re.fullmatch('[A-Z]{3}',data.get('currency') or '') or data.get('sale_type') not in {'service','upsell','cross_sell'}:
            raise ValueError('Неверная валюта или тип продажи.')
        if data.get('sale_type')=='upsell' and not data.get('receipt_id'):raise ValueError('Допродаже нужен связанный чек.')
        if data.get('has_upsell') is not None and not isinstance(data['has_upsell'],bool):raise ValueError('Неверный признак допродажи.')
        if envelope.get('target_id'):
            cursor.execute('SELECT to_jsonb(t) data FROM financialtransactions t WHERE id=%s AND business_id=%s FOR UPDATE',(target_id,business_id))
            before=_row(cursor,cursor.fetchone()).get('data') or {}
        if fingerprint(before)!=envelope['before_hash']:
            raise ValueError('Операция изменилась. Подготовьте новое подтверждение.')
        if before:
            cursor.execute('''UPDATE financialtransactions SET amount=%s,transaction_date=%s,transaction_type=%s,currency=%s,
                description=%s,receipt_id=%s,sale_type=%s,has_upsell=%s,is_voided=%s WHERE id=%s AND business_id=%s''',
                (data['amount'],data['transaction_date'],data['transaction_type'],data['currency'],data['description'],data['receipt_id'],data['sale_type'],data['has_upsell'],envelope['mode']=='void',target_id,business_id))
        else:
            cursor.execute('''INSERT INTO financialtransactions(id,user_id,business_id,amount,transaction_date,transaction_type,currency,description,receipt_id,sale_type,has_upsell)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(target_id,user_id,business_id,data['amount'],data['transaction_date'],data['transaction_type'],data['currency'],data['description'],data['receipt_id'],data['sale_type'],data['has_upsell']))
        after={**data,'id':target_id,'is_voided':envelope['mode']=='void'}
    else:
        raise ValueError('Неизвестный вид записи.')
    cursor.execute('''INSERT INTO finance_daily_events(id,business_id,target_id,kind,action_id,before_json,after_json,user_id,channel,message_ref)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)''',
        (str(uuid.uuid4()),business_id,target_id,kind,action_id,json.dumps(before,default=str),json.dumps(after,default=str),user_id,envelope['channel'],envelope.get('message_ref')))
    return after


def aggregate(summaries,transactions,entries,default_currency=None):
    days={}
    def bucket(day,currency):
        return days.setdefault((str(day)[:10],currency or 'UNKNOWN'),{'date':str(day)[:10],'currency':currency or 'UNKNOWN','detail':{},'receipts':set(),'upsell_receipts':set(),'known_upsell_receipts':set(),'sources':set(),'operations':[]})
    for source,rows in [('transactions',transactions),('entries',entries)]:
        for row in rows:
            if row.get('is_voided'):continue
            keydate=row.get('transaction_date') or row.get('date')
            group=bucket(keydate,row.get('currency'))
            kind=row.get('transaction_type') or row.get('type') or 'income'
            field={'income':'revenue','revenue':'revenue','expense':'expenses','refund':'refunds'}.get(kind)
            if not field:continue
            # Only overlapping measures are excluded; an expense-only source remains useful.
            if source=='entries' and field in group.get('transaction_fields',set()):
                group['overlapping_sources']=True;continue
            group['sources'].add(source);group['operations'].append(row)
            if source=='transactions':group.setdefault('transaction_fields',set()).add(field)
            group['detail'][field]=group['detail'].get(field,Decimal(0))+Decimal(str(row.get('amount') or 0))
            if source=='transactions' and field=='revenue':
                receipt=row.get('receipt_id')
                sale_type=row.get('sale_type') or 'service'
                if sale_type!='upsell':group['receipts'].add(receipt or row['id'])
                if sale_type=='upsell' and receipt:group['upsell_receipts'].add(receipt)
                if row.get('has_upsell') is True:group['upsell_receipts'].add(receipt or row['id'])
                if row.get('has_upsell') is not None:group['known_upsell_receipts'].add(receipt or row['id'])
    for row in summaries:
        if row.get('is_voided'):continue
        group=bucket(row['date'],row['currency']);group['summary']=row
    result=[]
    for group in days.values():
        detail=group['detail']
        if group['receipts']:detail['checks']=Decimal(len(group['receipts']))
        if group['receipts'] and group['receipts'] <= (group['known_upsell_receipts'] | group['upsell_receipts']):
            detail['upsell_checks']=Decimal(len(group['upsell_receipts'] & group['receipts']))
        summary=group.get('summary') or {};values=summary.get('values_json') or {}
        effective={field:(Decimal(values[field]) if values.get(field) is not None else detail.get(field)) for field in FIELDS}
        discrepancies={field:{'reported':str(values[field]),'detail':str(detail[field])} for field in FIELDS if values.get(field) is not None and field in detail and Decimal(values[field])!=detail[field]}
        effective['net_revenue']=effective['revenue']-effective['refunds'] if effective['revenue'] is not None and effective['refunds'] is not None else None
        effective['average_check']=effective['revenue']/effective['checks'] if effective['revenue'] is not None and effective['checks'] else None
        effective['upsell_share']=100*effective['upsell_checks']/effective['checks'] if effective['upsell_checks'] is not None and effective['checks'] else None
        result.append({'date':group['date'],'currency':group['currency'],'values':{k:float(v) if v is not None else None for k,v in effective.items()},
            'sources':{field:'daily_summary' if values.get(field) is not None else 'operations' if field in detail else 'unknown' for field in FIELDS},
            'summary_id':summary.get('id'),'version':summary.get('version'),'notes':values.get('notes'),'services':values.get('services',[]),
            'discrepancies':discrepancies,'reconciliation_status':'needs_review' if group['currency']=='UNKNOWN' or discrepancies or group.get('overlapping_sources') else 'reported' if summary else 'detail_only',
            'operations':group['operations'],'overlapping_sources':bool(group.get('overlapping_sources'))})
    currencies={}
    for currency in {row['currency'] for row in result}:
        rows=[row for row in result if row['currency']==currency]
        totals={field:float(sum((Decimal(str(row['values'][field])) for row in rows),Decimal(0))) if all(row['values'][field] is not None for row in rows) else None for field in FIELDS}
        totals['net_revenue']=totals['revenue']-totals['refunds'] if totals['revenue'] is not None and totals['refunds'] is not None else None
        totals['average_check']=totals['revenue']/totals['checks'] if totals['revenue'] is not None and totals['checks'] else None
        totals['upsell_share']=100*totals['upsell_checks']/totals['checks'] if totals['upsell_checks'] is not None and totals['checks'] else None
        currencies[currency]=totals
    return {'days':sorted(result,key=lambda row:(row['date'],row['currency']),reverse=True),'currencies':currencies}


def read_period(cursor,business_id,start,end):
    start=date.fromisoformat(str(start)[:10]);end=date.fromisoformat(str(end)[:10])
    if end<start or (end-start).days>3660:raise ValueError('Укажите корректный период до десяти лет.')
    cursor.execute('SELECT * FROM finance_daily_summaries WHERE business_id=%s AND date BETWEEN %s AND %s',(business_id,start,end))
    summaries=[_row(cursor,row) for row in cursor.fetchall()]
    cursor.execute('SELECT to_jsonb(t) data FROM financialtransactions t WHERE business_id=%s AND transaction_date::date BETWEEN %s AND %s',(business_id,start,end))
    transactions=[_row(cursor,row)['data'] for row in cursor.fetchall()]
    cursor.execute('SELECT to_jsonb(e) data FROM finance_entries e WHERE business_id=%s AND date BETWEEN %s AND %s',(business_id,start,end))
    entries=[_row(cursor,row)['data'] for row in cursor.fetchall()]
    cursor.execute('SELECT to_jsonb(s) data FROM finance_service_metrics s WHERE business_id=%s AND period_start=period_end AND period_start BETWEEN %s AND %s',(business_id,start,end))
    service_rows=[_row(cursor,row)['data'] for row in cursor.fetchall()]
    entry_days={(str(row['date'])[:10],row.get('currency')) for row in entries if row.get('type') in {'income','revenue'}}
    for row in service_rows:
        if (str(row['period_start'])[:10],row.get('currency')) not in entry_days and row.get('revenue') is not None:
            entries.append({'id':row['id'],'date':row['period_start'],'currency':row.get('currency'),'type':'income','amount':row['revenue'],'source':'service_metrics','description':row.get('service_name')})
    result=aggregate(summaries,transactions,entries)
    result['overlapping_daily_sources']=[row for row in service_rows if (str(row['period_start'])[:10],row.get('currency')) in entry_days]
    cursor.execute('''SELECT id,period_start,period_end,service_name,revenue FROM finance_service_metrics
        WHERE business_id=%s AND period_start<=%s AND period_end>=%s AND period_start<>period_end''',(business_id,end,start))
    result['period_aggregates']=[_row(cursor,row) for row in cursor.fetchall()]
    result['settings']=day_context(cursor,business_id)
    result['has_daily_summaries']=bool(summaries)
    result['voided_summaries']=[{'id':row['id'],'date':row['date'],'currency':row['currency']} for row in summaries if row.get('is_voided')]
    result['coverage']={'observed_days':len({row['date'] for row in result['days']}),'requested_days':(end-start).days+1}
    return result


def canonical_report(cursor,business_id,start,end):
    if not business_id or not installed(cursor):return None
    result=read_period(cursor,business_id,start,end)
    cursor.execute('SELECT 1 FROM finance_daily_events WHERE business_id=%s LIMIT 1',(business_id,))
    has_events=bool(cursor.fetchone())
    if enabled(business_id) or has_events or result['has_daily_summaries'] or result['settings'].get('version'):
        return result
    return None


def overlay_snapshot(snapshot,report):
    """Never combine currencies or keep revenue-dependent legacy estimates."""
    if report is None:return snapshot
    result=dict(snapshot);kpis=dict(result.get('kpis') or {})
    values=next(iter(report['currencies'].values())) if len(report['currencies'])==1 else {}
    for key in list(kpis):
        if key not in {'active_workplaces','available_workplace_hours','booked_workplace_hours','idle_workplace_hours','workplace_occupancy','staff_occupancy'}:
            kpis[key]=None
    kpis.update(revenue=values.get('revenue'),expenses=values.get('expenses'),average_ticket=values.get('average_check'),
        visits_count=values.get('checks'),refunds=values.get('refunds'),net_revenue=values.get('net_revenue'),upsell_share=values.get('upsell_share'))
    if values.get('net_revenue') is not None and values.get('expenses') is not None:
        kpis['operating_profit']=values['net_revenue']-values['expenses']
    result.update(kpis=kpis,financial_daily=report,currency=next(iter(report['currencies'])) if len(report['currencies'])==1 else None)
    result['recommendations']=[]
    result['explanations']={key:'Показатель не рассчитан: недостаточно сопоставимых данных.' for key,value in kpis.items() if value is None}
    return result


def handle_apply(envelope,user_data):
    from database_manager import DatabaseManager
    user_id=(envelope.get('actor') or {}).get('id') or user_data.get('user_id') or user_data.get('id')
    db=DatabaseManager()
    try:
        saved=apply(db.conn.cursor(),envelope.get('tenant_id'),user_id,envelope.get('payload') or {},envelope.get('action_id'))
        db.conn.commit()
        return {'status':'completed','chat_response':'Финансовые данные сохранены. '+('Запись отменена; история сохранена.' if saved.get('is_voided') else 'Итоги и детализация доступны в финансах.'),
                'saved':saved,'localos_write_performed':True,'provider_write_performed':False}
    except (ValueError,PermissionError):
        import sys
        db.conn.rollback()
        return {'status':'blocked','chat_response':str(sys.exception()),'localos_write_performed':False,'provider_write_performed':False}
    finally:
        db.close()
