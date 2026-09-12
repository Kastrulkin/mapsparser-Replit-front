"""Shared, explainable upsell recommendations and approved owner policy."""
import json
import math
import uuid
from datetime import datetime, timezone
from services.operator_conversations import _row
from services import work_journal


def policy(cursor,business_id):
    cursor.execute('SELECT * FROM business_upsell_policies WHERE business_id=%s',(business_id,))
    return _row(cursor,cursor.fetchone()) or {'business_id':business_id,'version':0,'rules_json':[]}


def catalog(cursor,business_id):
    cursor.execute('SELECT to_jsonb(s) data FROM userservices s WHERE business_id=%s AND COALESCE(is_active,TRUE)=TRUE ORDER BY name LIMIT 1000',(business_id,))
    return [_row(cursor,row)['data'] for row in cursor.fetchall()]


def matrix(cursor,business_id):
    cursor.execute('SELECT * FROM averageticketmatrices WHERE business_id=%s ORDER BY generated_at DESC,id DESC LIMIT 1',(business_id,))
    return _row(cursor,cursor.fetchone())


def resolve_service(services,service_id=None,name=None):
    if service_id:
        matches=[s for s in services if s['id']==service_id]
    else:
        matches=[s for s in services if str(s.get('name') or '').casefold()==str(name or '').casefold()]
        if not matches and name:matches=[s for s in services if str(name).casefold() in str(s.get('name') or '').casefold()]
    if len(matches)!=1:raise ValueError('Уточните услугу: '+str(name or service_id or 'название не указано'))
    return matches[0]


def applicable(rule,main_id,master_id,now):
    if rule.get('main_service_id') and rule['main_service_id']!=main_id:return False
    if rule.get('master_id') and rule['master_id']!=master_id:return False
    if rule.get('starts_at') and now<datetime.fromisoformat(rule['starts_at']):return False
    if rule.get('ends_at') and now>=datetime.fromisoformat(rule['ends_at']):return False
    return True


def select(services,current_matrix,rules,main_id,master_id=None,free_minutes=None,now=None):
    now=now or datetime.now(timezone.utc)
    available={item['id']:item for item in services}
    if main_id not in available:return []
    active=[r for r in rules if applicable(r,main_id,master_id,now)]
    result=[]
    for row in (current_matrix or {}).get('upsell_matrix') or []:
        if row.get('main_service_id')!=main_id:continue
        for link in row.get('recommended_addons') or []:
            service=available.get(link.get('service_id'))
            if not service or link.get('status')!='active':continue
            matching=[r for r in active if not r.get('addon_service_id') or r['addon_service_id']==service['id']]
            if any(r['action']=='ban' for r in matching):continue
            if any(r['action']=='minimum_gap' and (free_minutes is None or free_minutes<r['minutes']) for r in matching):continue
            duration=service.get('duration_minutes',service.get('duration'))
            if duration is not None:
                try:duration=float(duration)
                except (ValueError,TypeError):duration=None
                if duration is not None and (not math.isfinite(duration) or duration<0):duration=None
            if free_minutes is not None and duration is not None and duration>free_minutes:continue
            priority={'high':3,'medium':2,'low':1}.get(link.get('priority'),1)
            preferred=[r for r in matching if r['action']=='prefer']
            scripts=[r for r in matching if r['action']=='wording']
            result.append({'id':link.get('id'),'link_id':link.get('id'),'service_id':service['id'],'service_name':service.get('name'),'service':service.get('name'),
                'price':service.get('price'),'duration_minutes':duration,'time_verified':free_minutes is not None and duration is not None,
                'reason':link.get('reason') or 'Действующая связка услуг.',
                'admin_script':scripts[-1].get('admin_script') if scripts else link.get('admin_script'),
                'master_script':scripts[-1].get('master_script') if scripts else link.get('master_script'),
                'offer_timing':link.get('offer_timing'),'applied_rules':[{'id':r['id'],'instruction':r['instruction']} for r in matching],
                'priority':priority+(10 if preferred else 0)})
    return sorted(result,key=lambda value:(-value['priority'],str(value['service_name'])))[:3]


def recommend(cursor,business_id,user_id,args,preview_rules=None):
    actor=work_journal.scope(cursor,business_id,user_id)
    current=policy(cursor,business_id)
    if not work_journal.enabled(business_id) and current['rules_json']:
        return {'status':'blocked','items':[],'message':'Рекомендации приостановлены: применение подтверждённых правил отключено.'}
    services=catalog(cursor,business_id);current_matrix=matrix(cursor,business_id)
    rules=preview_rules if preview_rules is not None else current['rules_json']
    visits=[];groups=args.get('services') or []
    if args.get('booking_id'):
        visits=[work_journal.booking(cursor,business_id,actor,args['booking_id'])]
    elif not groups:
        visits=work_journal.list_bookings(cursor,business_id,actor,work_journal.local_day(cursor,business_id,args.get('date')))
    if len(groups)>50:raise ValueError('Укажите до 50 групп услуг.')
    if args.get('next_visit'):
        now=datetime.now(timezone.utc)
        visits=sorted([v for v in visits if work_journal.visit_time(cursor,business_id,v) and work_journal.visit_time(cursor,business_id,v)>=now],key=lambda v:work_journal.visit_time(cursor,business_id,v))[:1]
    items=[]
    for row in visits or groups:
        if visits and row.get('status') in {'cancelled','canceled','rejected'}:continue
        service=resolve_service(services,row.get('service_id'),row.get('service_name') or row.get('name'))
        minutes=args.get('free_minutes')
        if minutes is not None and (not isinstance(minutes,(int,float)) or isinstance(minutes,bool) or not math.isfinite(minutes) or minutes<0 or minutes>1440):raise ValueError('Укажите доступное время в минутах.')
        recommendations=select(services,current.get('matrix_json') if current.get('matrix_json') is not None else current_matrix.get('matrix_json'),rules,service['id'],row.get('master_id'),minutes,now=work_journal.visit_time(cursor,business_id,row) if visits else None)
        events=[]
        if visits:
            cursor.execute('SELECT event_type,addon_service_id,notes FROM averageticketevents WHERE business_id=%s AND booking_id=%s AND NOT is_voided ORDER BY created_at DESC',(business_id,row['id']))
            events=[_row(cursor,event) for event in cursor.fetchall()]
        for recommendation in recommendations:
            recommendation['previous_results']=[event for event in events if event.get('addon_service_id')==recommendation['service_id']]
        items.append({'booking_id':row.get('id') if visits else None,'service_id':service['id'],'service_name':service.get('name'),
            'time':row.get('booking_time_local') or row.get('booking_time'),'master_id':row.get('master_id'),'count':row.get('count') if not visits else None,
            'recommendations':recommendations,'results':events})
    return {'status':'completed','items':items,'policy_version':current['version'],'message':'Нет доступных записей. Можно назвать услуги без создания визитов.' if not items else 'Рекомендации по действующим связкам и правилам.'}


def validate_rules(cursor,business_id,rules):
    if not isinstance(rules,list) or len(rules)>100:raise ValueError('Допускается до 100 правил.')
    ids=set();services={row['id'] for row in catalog(cursor,business_id)}
    for rule in rules:
        allowed={'id','action','main_service_id','addon_service_id','master_id','starts_at','ends_at','permanent','minutes','instruction','admin_script','master_script'}
        if set(rule)-allowed:raise ValueError('Условие не поддерживается. Оно не будет считаться действующим ограничением.')
        if rule.get('action') not in {'ban','prefer','wording','minimum_gap'}:raise ValueError('Поддерживаются запрет, приоритет, формулировка и минимальное свободное время.')
        if not rule.get('id') or rule['id'] in ids:raise ValueError('Идентификаторы правил должны быть уникальны.')
        ids.add(rule['id'])
        if not rule.get('instruction') or len(str(rule['instruction']))>2000:raise ValueError('Нужно понятное описание правила.')
        for field in ('main_service_id','addon_service_id'):
            if rule.get(field) and rule[field] not in services:raise ValueError('Услуга правила отсутствует или архивирована.')
        if rule['action'] in {'ban','prefer'} and not rule.get('addon_service_id'):raise ValueError('Уточните дополнение, к которому относится правило.')
        if rule.get('master_id'):
            cursor.execute('SELECT id FROM masters WHERE business_id=%s AND id=%s',(business_id,rule['master_id']))
            if not cursor.fetchone():raise ValueError('Мастер не найден в этой точке.')
        if rule['action']=='minimum_gap' and (not isinstance(rule.get('minutes'),int) or isinstance(rule.get('minutes'),bool) or not 1<=rule['minutes']<=1440):raise ValueError('Укажите минимальное свободное время в минутах.')
        if rule['action']=='wording' and not (rule.get('admin_script') or rule.get('master_script')):raise ValueError('Укажите новую формулировку предложения.')
        if not rule.get('permanent') and not rule.get('ends_at'):raise ValueError('Уточните срок: постоянно или до какого момента действует правило?')
        for field in ('starts_at','ends_at'):
            if rule.get(field):
                parsed=datetime.fromisoformat(rule[field])
                if not parsed.tzinfo:raise ValueError('Временное правило должно содержать часовой пояс.')
        if rule.get('starts_at') and rule.get('ends_at') and datetime.fromisoformat(rule['starts_at'])>=datetime.fromisoformat(rule['ends_at']):raise ValueError('Конец правила должен быть позже начала.')
    return rules


def prepare_policy(cursor,business_id,user_id,args):
    work_journal.scope(cursor,business_id,user_id,True,True)
    before=policy(cursor,business_id);current_matrix=matrix(cursor,business_id)
    kind=args.get('kind','rules')
    after=json.loads(json.dumps(before['rules_json']))
    data={}
    if kind=='rules':
        if args.get('restore_history_id'):
            cursor.execute("SELECT before_json FROM business_work_history WHERE id=%s AND business_id=%s AND kind='rules'",(args['restore_history_id'],business_id))
            saved=_row(cursor,cursor.fetchone()).get('before_json')
            if not saved:raise ValueError('Версия для отката не найдена.')
            after=saved.get('rules_json') or []
        else:
            for change in args.get('changes') or []:
                change=dict(change);remove=change.pop('remove',False);rule_id=change.get('id') or str(uuid.uuid4());change['id']=rule_id
                old=next((r for r in after if r['id']==rule_id),None)
                if remove and not old:raise ValueError('Правило для удаления не найдено.')
                after=[r for r in after if r['id']!=rule_id]
                if not remove:after.append({**(old or {}),**change})
        validate_rules(cursor,business_id,after)
        if after==before['rules_json']:raise ValueError('Изменений правил нет.')
        data={'rules':after}
    elif kind=='binding':
        member=args.get('user_id');master=args.get('master_id')
        cursor.execute("SELECT user_id FROM business_members WHERE business_id=%s AND user_id=%s AND status='active'",(business_id,member))
        if not cursor.fetchone():raise ValueError('Сначала добавьте сотрудника в выбранный бизнес.')
        name=str(args.get('master_name') or '').strip()
        if master:
            cursor.execute('SELECT id FROM masters WHERE business_id=%s AND id=%s',(business_id,master))
            if not cursor.fetchone():raise ValueError('Выберите мастера этой точки.')
        elif not name or len(name)>200:raise ValueError('Укажите имя нового мастера или выберите существующего.')
        data={'user_id':member,'master_id':master or str(uuid.uuid4()),'master_name':name if not master else None,'create_master':not bool(master)}
    elif kind=='assignment':
        actor=work_journal.scope(cursor,business_id,user_id,True,True)
        visit=work_journal.booking(cursor,business_id,actor,args.get('booking_id'))
        cursor.execute('SELECT id FROM masters WHERE business_id=%s AND id=%s',(business_id,args.get('master_id')))
        if not cursor.fetchone():raise ValueError('Выберите мастера этой точки.')
        data={'booking_id':visit['id'],'master_id':args['master_id'],'previous_master_id':visit.get('master_id')}
    elif kind=='matrix':
        if args.get('matrix_id')!=current_matrix.get('id'):raise ValueError('Матрица уже изменилась. Откройте текущую.')
        proposed=args.get('matrix_json')
        if not isinstance(proposed,dict):raise ValueError('Нужны новые связки.')
        services={row['id'] for row in catalog(cursor,business_id)}
        for row in proposed.get('upsell_matrix') or []:
            if row.get('main_service_id') not in services:raise ValueError('Основная услуга недоступна.')
            for addon in row.get('recommended_addons') or []:
                if addon.get('service_id') not in services or addon.get('status') not in {'active','disabled','draft'}:raise ValueError('Проверьте услугу и статус дополнения.')
        data={'matrix_json':proposed,'matrix_id':current_matrix['id']}
    else:raise ValueError('Неизвестное изменение.')
    examples=[]
    if kind in {'rules','matrix'}:
        services=catalog(cursor,business_id)
        for row in (current_matrix.get('matrix_json') or {}).get('upsell_matrix',[])[:5]:
            affected=next((r for r in after if not r.get('main_service_id') or r['main_service_id']==row.get('main_service_id')),{})
            moment=datetime.fromisoformat(affected['starts_at']) if affected.get('starts_at') else datetime.now(timezone.utc)
            examples.append({'service_id':row.get('main_service_id'),'master_id':affected.get('master_id'),'at':moment.isoformat(),
                'before':select(services,before.get('matrix_json') if before.get('matrix_json') is not None else current_matrix.get('matrix_json'),before['rules_json'],row.get('main_service_id'),affected.get('master_id'),now=moment),
                'after':select(services,data.get('matrix_json',before.get('matrix_json') if before.get('matrix_json') is not None else current_matrix.get('matrix_json')),after,row.get('main_service_id'),affected.get('master_id'),now=moment)})
    return {'kind':kind,'version':before['version'],'matrix_hash':work_journal.digest(current_matrix),'data':data,'examples':examples,'before':before}


def apply_policy(cursor,business_id,user_id,envelope,action_id):
    work_journal.scope(cursor,business_id,user_id,True,True)
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('work-journal:'+business_id,))
    work_journal.scope(cursor,business_id,user_id,True,True)
    cursor.execute('SELECT after_json FROM business_work_history WHERE business_id=%s AND request_key=%s',(business_id,action_id))
    replay=_row(cursor,cursor.fetchone())
    if replay:
        if replay['after_json'].get('request_hash')!=work_journal.digest(envelope):raise ValueError('Подтверждение уже использовано для другого изменения.')
        return replay['after_json']
    before=policy(cursor,business_id)
    if before['version']!=envelope['version'] or work_journal.digest(matrix(cursor,business_id))!=envelope['matrix_hash']:raise ValueError('Правила или связки изменились. Подготовьте новое подтверждение.')
    data=envelope['data'];kind=envelope['kind'];rules=before['rules_json']
    selected_matrix=before.get('matrix_json') if before.get('matrix_json') is not None else matrix(cursor,business_id).get('matrix_json')
    if kind=='rules':rules=validate_rules(cursor,business_id,data['rules'])
    elif kind=='matrix':
        selected_matrix=data['matrix_json']
        prepare_policy(cursor,business_id,user_id,{'kind':'matrix',**data})
        before={**before,'matrix_json':matrix(cursor,business_id).get('matrix_json')}
        cursor.execute('UPDATE averageticketmatrices SET matrix_json=%s::jsonb,updated_at=NOW() WHERE id=%s AND business_id=%s',(json.dumps(data['matrix_json']),data['matrix_id'],business_id))
    elif kind=='binding':
        cursor.execute('SELECT * FROM business_master_bindings WHERE business_id=%s AND user_id=%s',(business_id,data['user_id']))
        before={**before,'binding':_row(cursor,cursor.fetchone())}
        prepare_policy(cursor,business_id,user_id,{'kind':'binding',**data,'master_id':None if data.get('create_master') else data['master_id']})
        if data.get('create_master'):
            cursor.execute('INSERT INTO masters(id,business_id,name) VALUES (%s,%s,%s)',(data['master_id'],business_id,data['master_name']))
        cursor.execute('''INSERT INTO business_master_bindings(business_id,user_id,master_id) VALUES (%s,%s,%s)
            ON CONFLICT(business_id,user_id) DO UPDATE SET master_id=EXCLUDED.master_id,version=business_master_bindings.version+1,updated_at=NOW()''',(business_id,data['user_id'],data['master_id']))
    elif kind=='assignment':
        checked=prepare_policy(cursor,business_id,user_id,{'kind':'assignment',**data})
        if checked['data']['previous_master_id']!=data['previous_master_id']:raise ValueError('Назначение визита изменилось. Подготовьте новое подтверждение.')
        before={**before,'assignment':checked['data']}
        cursor.execute('UPDATE bookings SET master_id=%s WHERE business_id=%s AND id=%s',(data['master_id'],business_id,data['booking_id']))
    else:raise ValueError('Неизвестное изменение.')
    cursor.execute('''INSERT INTO business_upsell_policies(business_id,version,rules_json,matrix_json) VALUES (%s,1,%s::jsonb,%s::jsonb)
        ON CONFLICT(business_id) DO UPDATE SET version=business_upsell_policies.version+1,rules_json=EXCLUDED.rules_json,matrix_json=EXCLUDED.matrix_json,updated_at=NOW() RETURNING *''',(business_id,json.dumps(rules),json.dumps(selected_matrix)))
    after=_row(cursor,cursor.fetchone());after['applied_change']=data;after['request_hash']=work_journal.digest(envelope)
    work_journal._audit(cursor,business_id,user_id,envelope.get('channel','web'),kind,business_id,action_id,before,after)
    return after


def handle_policy(envelope,user_data):
    from database_manager import DatabaseManager
    db=DatabaseManager()
    try:
        result=apply_policy(db.conn.cursor(),envelope['tenant_id'],(envelope.get('actor') or {}).get('id') or user_data.get('user_id'),envelope['payload'],envelope['action_id'])
        db.conn.commit()
        return {'status':'completed','chat_response':'Изменения подтверждены. Будущие рекомендации используют новую версию правил.','saved':result,'localos_write_performed':True}
    except (ValueError,PermissionError):
        import sys
        db.conn.rollback();return {'status':'blocked','chat_response':str(sys.exception()),'localos_write_performed':False}
    finally:db.close()
