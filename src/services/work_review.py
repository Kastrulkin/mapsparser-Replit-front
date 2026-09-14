"""Explicit manager grants and durable review decisions for work observations."""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from services.operator_conversations import _row
from services import work_journal

STATUSES={'new','clarification','observing','in_progress','rejected','completed'}
CATEGORIES={'complaint','wish','idea','operations','other'}


def enabled(business):
    return business in {value.strip() for value in os.getenv('OPERATOR_WORK_REVIEW_BUSINESS_IDS','').split(',') if value.strip()}


def available(cursor):
    cursor.execute("SELECT to_regclass('business_work_reviewers') present")
    return bool(_row(cursor,cursor.fetchone()).get('present'))


def can_review(cursor,business,user):
    actor=work_journal.scope(cursor,business,user)
    if actor['role']=='owner':return True
    if not available(cursor):return False
    cursor.execute('SELECT enabled FROM business_work_reviewers WHERE business_id=%s AND user_id=%s',(business,user))
    return actor['role'] in {'manager','admin'} and bool(_row(cursor,cursor.fetchone()).get('enabled'))


def require_review(cursor,business,user):
    if not enabled(business):raise PermissionError('Разбор журнала пока отключён для этого бизнеса.')
    if not can_review(cursor,business,user):raise PermissionError('Владелец должен предоставить право разбора журнала.')


def sanitize(entry,reviewer):
    result=dict(entry)
    if not reviewer:result.pop('decision',None)
    result['can_review']=reviewer
    return result


def list_inbox(cursor,business,user,status='new',category=None):
    require_review(cursor,business,user)
    if status and status not in STATUSES:raise ValueError('Неизвестный статус.')
    if category and category not in CATEGORIES:raise ValueError('Неизвестная категория.')
    cursor.execute('''SELECT j.*,COALESCE(NULLIF(to_jsonb(u)->>'name',''),to_jsonb(u)->>'email','Сотрудник') author_name FROM business_work_journal j LEFT JOIN users u ON u.id=j.user_id WHERE j.business_id=%s AND NOT j.is_voided
        AND (%s IS NULL OR j.review_status=%s) AND (%s IS NULL OR j.category=%s) ORDER BY j.urgent DESC,j.created_at DESC LIMIT 100''',
        (business,status,status,category,category))
    rows=[sanitize(_row(cursor,row),True) for row in cursor.fetchall()]
    for row in rows:
        # Grouping is a presentation aid; never merge clients or source records.
        row['similarity_group']=work_journal.digest({'category':row['category'],'quote':re.sub(r'\W+',' ',str(row['facts_json'].get('quote') or '').casefold())})[:12]
    groups={}
    for row in rows:groups.setdefault(row['similarity_group'],[]).append(row)
    for group in groups.values():group[0]['group_count']=len(group)
    return [row for group in groups.values() for row in group]


def decision(cursor,business,user,entry_id,args,channel='web'):
    require_review(cursor,business,user)
    key=args.get('request_id')
    if not key:raise ValueError('Нужен идентификатор запроса.')
    cursor.execute('SELECT * FROM business_work_journal WHERE business_id=%s AND id=%s FOR UPDATE',(business,entry_id))
    entry=_row(cursor,cursor.fetchone())
    if not entry or entry['is_voided']:raise ValueError('Запись не найдена или отменена.')
    cursor.execute("SELECT after_json FROM business_work_history WHERE business_id=%s AND request_key=%s AND kind='review'",(business,key))
    prior=_row(cursor,cursor.fetchone())
    fingerprint=work_journal.digest({'entry_id':entry_id,'user_id':user,'args':args})
    if prior:
        if prior['after_json'].get('request_hash')!=fingerprint:raise ValueError('Идентификатор запроса уже использован.')
        return sanitize(entry,True)
    if args.get('version')!=entry['version']:raise ValueError('Запись изменилась. Обновите её перед решением.')
    status=args.get('status',entry['review_status']);category=args.get('category',entry['category'])
    if status not in STATUSES or category not in CATEGORIES:raise ValueError('Неизвестное решение или категория.')
    assigned=args.get('assigned_to',entry.get('assigned_to'))
    if assigned:work_journal.scope(cursor,business,assigned,write=True)
    note=str(args.get('decision') or '').strip()[:3000]
    if status in {'rejected','completed'} and not note:raise ValueError('Укажите причину отклонения или результат закрытия.')
    cursor.execute('''UPDATE business_work_journal SET review_status=%s,category=%s,assigned_to=%s,decision=%s,
        version=version+1,updated_at=NOW() WHERE id=%s RETURNING *''',(status,category,assigned,note,entry_id))
    after=_row(cursor,cursor.fetchone())
    work_journal._audit(cursor,business,user,channel,'review',entry_id,key,entry,{**after,'request_hash':fingerprint})
    return sanitize(after,True)


def prepare_grant(cursor,business,user,args):
    work_journal.scope(cursor,business,user,write=True,owner_only=True)
    target=args.get('user_id')
    actor=work_journal.scope(cursor,business,target)
    if actor['role'] not in {'manager','admin'}:raise ValueError('Выберите действующего управляющего этой точки.')
    cursor.execute('SELECT version FROM business_work_reviewers WHERE business_id=%s AND user_id=%s',(business,target))
    version=_row(cursor,cursor.fetchone()).get('version',0)
    return {'kind':'reviewer','business_id':business,'user_id':target,'enabled':args.get('enabled') is not False,'version':version}


def apply_grant(cursor,business,user,envelope,action_id):
    require_review(cursor,business,user)
    work_journal.scope(cursor,business,user,write=True,owner_only=True)
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('reviewer:'+business,))
    cursor.execute("SELECT after_json FROM business_work_history WHERE business_id=%s AND request_key=%s AND kind='reviewer'",(business,action_id))
    if cursor.fetchone():return {'status':'completed','chat_response':'Решение уже применено.'}
    current=prepare_grant(cursor,business,user,envelope)
    if current['version']!=envelope['version'] or envelope.get('business_id')!=business:raise ValueError('Права изменились. Подготовьте новое подтверждение.')
    cursor.execute('''INSERT INTO business_work_reviewers(business_id,user_id,enabled,granted_by) VALUES (%s,%s,%s,%s)
        ON CONFLICT(business_id,user_id) DO UPDATE SET enabled=EXCLUDED.enabled,version=business_work_reviewers.version+1,granted_by=EXCLUDED.granted_by''',
        (business,envelope['user_id'],envelope['enabled'],user))
    work_journal._audit(cursor,business,user,'web','reviewer',envelope['user_id'],action_id,current,envelope)
    return {'status':'completed','chat_response':'Право разбора журнала обновлено.'}


def create_action(cursor,business,user,entry_id,args):
    require_review(cursor,business,user)
    cursor.execute('SELECT * FROM business_work_journal WHERE id=%s AND business_id=%s FOR UPDATE',(entry_id,business))
    entry=_row(cursor,cursor.fetchone())
    if not entry or entry['is_voided']:raise ValueError('Запись не найдена.')
    key=args.get('request_id')
    if not key:raise ValueError('Нужен идентификатор запроса.')
    dedupe=work_journal.digest({'business':business,'request':key,'entry':entry_id,'user':user})
    cursor.execute('SELECT * FROM journey_actions WHERE business_id=%s AND dedupe_key=%s',(business,dedupe))
    prior=_row(cursor,cursor.fetchone())
    if prior:
        if prior['payload_json'].get('request_hash')!=work_journal.digest(args):raise ValueError('Идентификатор запроса уже использован.')
        return prior
    if entry['version']!=args.get('version'):raise ValueError('Запись изменилась. Обновите её.')
    if entry['review_status']!='in_progress':raise ValueError('Сначала примите наблюдение в работу.')
    existing_id=args.get('existing_action_id')
    if existing_id:
        cursor.execute("SELECT * FROM journey_actions WHERE id=%s AND business_id=%s AND flow_type='work_journal' AND entity_type='work_observation' FOR UPDATE",(existing_id,business))
        action=_row(cursor,cursor.fetchone())
        if not action:raise PermissionError('Связанная задача не найдена.')
        if args.get('action_version')!=action['version']:raise ValueError('Задача изменилась. Обновите её.')
        cursor.execute("SELECT after_json FROM business_work_history WHERE business_id=%s AND request_key=%s AND kind='task_link'",(business,dedupe))
        linked=_row(cursor,cursor.fetchone())
        if linked:
            if linked['after_json'].get('request_hash')!=work_journal.digest(args):raise ValueError('Идентификатор запроса уже использован.')
            return action
        cursor.execute('INSERT INTO business_work_links(business_id,entry_id,action_id,created_by) VALUES (%s,%s,%s,%s) ON CONFLICT(entry_id,action_id) DO NOTHING',(business,entry_id,existing_id,user))
        work_journal._audit(cursor,business,user,'web','task_link',entry_id,dedupe,{}, {'action_id':str(action['id']),'request_hash':work_journal.digest(args)})
        return action
    kind=args.get('kind','task')
    if kind not in {'task','map_update','post_draft','client_message','bonus','work_rules'}:raise ValueError('Неизвестное действие.')
    assignee=args.get('assigned_to') or entry.get('assigned_to') or user
    work_journal.scope(cursor,business,assignee,write=True)
    title=str(args.get('title') or '').strip();text=str(args.get('text') or '').strip()
    if not title or len(title)>250 or len(text)>6000:raise ValueError('Укажите короткое название и описание задачи.')
    due=args.get('due_at')
    if due and not datetime.fromisoformat(due.replace('Z','+00:00')).tzinfo:raise ValueError('Укажите срок с часовым поясом.')
    if kind=='bonus' and work_journal.scope(cursor,business,user)['role']!='owner':
        title='На решение владельцу: '+title
        cursor.execute('SELECT owner_id FROM businesses WHERE id=%s',(business,))
        assignee=_row(cursor,cursor.fetchone()).get('owner_id')
        work_journal.scope(cursor,business,assignee,write=True)
    action_id=str(uuid.uuid4())
    payload={'request_hash':work_journal.digest(args),'kind':kind,'source_entry_id':entry_id,'execution_mode':'manual','approved_external':False}
    cursor.execute('''INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,entity_id,action_type,status,title,description,cta_label,cta_target_json,payload_json,dedupe_key,due_at)
        VALUES (%s,%s,%s,'work_journal','work_observation',%s,%s,'ready',%s,%s,'Открыть задачу',%s::jsonb,%s::jsonb,%s,%s) RETURNING *''',
        (action_id,business,assignee,entry_id,kind,title,text,json.dumps({'href':'/dashboard/work-journal?entry='+entry_id}),json.dumps(payload),dedupe,due))
    action=_row(cursor,cursor.fetchone())
    if kind=='post_draft' and text:
        from services.operator_news_generation import _insert_news_draft, NEWS_DRAFTS_URL
        cursor.execute('SAVEPOINT observation_draft')
        try:
            draft=_insert_news_draft(cursor,business_id=business,user_id=user,source_text='Со слов сотрудника: '+str(entry['facts_json'].get('quote') or ''),generated_text=text,prompt_key='work_observation_draft')
            payload.update(draft_id=draft['id'],draft_href=NEWS_DRAFTS_URL,execution_mode='draft')
            cursor.execute('UPDATE journey_actions SET description=%s,payload_json=%s::jsonb WHERE id=%s RETURNING *',('Черновик сохранён в контенте. Публикация требует отдельного решения.',json.dumps(payload),action_id))
            action=_row(cursor,cursor.fetchone())
            cursor.execute('RELEASE SAVEPOINT observation_draft')
        except Exception:
            cursor.execute('ROLLBACK TO SAVEPOINT observation_draft');cursor.execute('RELEASE SAVEPOINT observation_draft')
    cursor.execute('INSERT INTO business_work_links(business_id,entry_id,action_id,created_by) VALUES (%s,%s,%s,%s)',(business,entry_id,action_id,user))
    return action


def links(cursor,business,user,entry_id):
    actor=work_journal.scope(cursor,business,user);work_journal.read_entry(cursor,business,actor,entry_id)
    reviewer=can_review(cursor,business,user)
    cursor.execute('''SELECT a.* FROM journey_actions a JOIN business_work_links l ON l.action_id=a.id
        WHERE l.business_id=%s AND l.entry_id=%s AND a.business_id=%s ORDER BY a.created_at''',(business,entry_id,business))
    rows=[_row(cursor,row) for row in cursor.fetchall()]
    return rows if reviewer else [{key:row.get(key) for key in ('id','status','completed_at')} for row in rows]


def tools(cursor,business,user,channel,request_key):
    from services.operator_work_journal import result
    text={'type':'string'}
    def review(args):
        row=decision(cursor,business,user,args['entry_id'],{**args,'request_id':request_key+':review:'+args['entry_id']},channel)
        return result('Решение сохранено: '+row['review_status'],entry=row)
    def action(args):
        row=create_action(cursor,business,user,args['entry_id'],{**args,'request_id':request_key+':action:'+work_journal.digest(args)})
        return result('Задача создана. Внешнее действие требует отдельного подтверждения или ручного выполнения.',action=row)
    return [
        {'name':'work.action_results','title':'Связанные задачи и результаты','description':'Читает задачи наблюдения, текущие версии, сохранённые черновики и результаты. Чужие внутренние комментарии сотрудникам не возвращаются.', 'input_schema':{'type':'object','required':['entry_id'],'properties':{'entry_id':text}},'execute':lambda args:result('Связанные действия.',items=links(cursor,business,user,args['entry_id']))},
        {'name':'work.complete_action','title':'Зафиксировать результат задачи','description':'Только по явному сообщению руководителя о ручном выполнении задачи. Сначала прочитай action_results. Сохраняет сообщённый результат, не выдумывает подтверждение API и не закрывает наблюдение автоматически.', 'input_schema':{'type':'object','required':['entry_id','action_id','version','result'],'properties':{'entry_id':text,'action_id':text,'version':{'type':'integer'},'result':text}},'risk_class':'internal_observation_write','execute':lambda args:result('Результат задачи сохранён со слов руководителя.',action=complete_action(cursor,business,user,args['entry_id'],{**args,'request_id':request_key+':complete:'+args['action_id']}))},
        {'name':'work.review_inbox','title':'Наблюдения на разбор','description':'Только владелец или управляющий с явным правом разбора. Читает исходные сообщения, версии и статусы, не меняет их.',
         'input_schema':{'type':'object','properties':{'status':text,'category':text}},'execute':lambda args:result('Записи на разбор.',items=list_inbox(cursor,business,user,args.get('status','new'),args.get('category')))},
        {'name':'work.review_decision','title':'Разобрать наблюдение','description':'По явному решению руководителя: clarification, observing, in_progress, rejected, completed. Для отклонения и закрытия обязательна причина decision. До действий сначала принять in_progress. Не считать принятие выполнением.',
         'input_schema':{'type':'object','required':['entry_id','version','status'],'properties':{**{key:text for key in ('entry_id','status','category','decision','assigned_to')},'version':{'type':'integer'}}},'execute':review,'risk_class':'internal_observation_write'},
        {'name':'work.create_action','title':'Задача по наблюдению','description':'Создать задачу назначенному участнику по принятому наблюдению, только по выбору руководителя. kind task/map_update/post_draft/client_message/bonus/work_rules. Не выводи изменение часов из плохой встречи. Для связи с ранее созданной задачей укажи existing_action_id и action_version. Черновик не отправляется. Бонус не обещается. Укажи title, text и согласованный due_at с часовым поясом.',
         'input_schema':{'type':'object','required':['entry_id','version'],'properties':{**{key:text for key in ('entry_id','kind','title','text','assigned_to','due_at','existing_action_id')},'action_version':{'type':'integer'},'version':{'type':'integer'}}},'execute':action,'risk_class':'internal_observation_write'}]


def complete_action(cursor,business,user,entry_id,args):
    require_review(cursor,business,user)
    action_id=args.get('action_id');request_id=args.get('request_id')
    if not action_id or not request_id:raise ValueError('Укажите задачу и идентификатор запроса.')
    cursor.execute('''SELECT a.* FROM journey_actions a JOIN business_work_links l ON l.action_id=a.id
        WHERE l.business_id=%s AND l.entry_id=%s AND a.id=%s AND a.business_id=%s FOR UPDATE OF a''',(business,entry_id,action_id,business))
    before=_row(cursor,cursor.fetchone())
    if not before:raise PermissionError('Нет доступа к задаче.')
    cursor.execute("SELECT after_json FROM business_work_history WHERE business_id=%s AND kind='task_result' AND request_key=%s",(business,request_id))
    replay=_row(cursor,cursor.fetchone())
    fingerprint=work_journal.digest({'user':user,'entry':entry_id,'args':args})
    if replay:
        if replay['after_json'].get('request_hash')!=fingerprint:raise ValueError('Идентификатор запроса уже использован.')
        return before
    if args.get('version')!=before['version']:raise ValueError('Задача изменилась. Обновите её.')
    evidence=str(args.get('result') or '').strip()
    if not evidence or len(evidence)>3000:raise ValueError('Укажите результат ручного выполнения.')
    if before['status']=='completed':raise ValueError('Задача уже завершена.')
    payload={**before['payload_json'],'reported_result':evidence,'reported_by':user,'result_source':'manual_report'}
    cursor.execute("UPDATE journey_actions SET status='completed',payload_json=%s::jsonb,version=version+1,completed_at=NOW(),updated_at=NOW() WHERE id=%s RETURNING *",(json.dumps(payload),action_id))
    after=_row(cursor,cursor.fetchone())
    work_journal._audit(cursor,business,user,'web','task_result',entry_id,request_id,before,{**after,'request_hash':fingerprint})
    return after


def digest_settings(cursor,business,user,args=None):
    require_review(cursor,business,user)
    if args is not None:
        work_journal.scope(cursor,business,user,write=True,owner_only=True)
        from services.business_input_settings import resolve
        if not resolve(cursor,business).get('timezone'):raise ValueError('Сначала укажите часовой пояс бизнеса в настройках.')
        value=str(args.get('local_time') or '18:00')
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value):raise ValueError('Укажите время ЧЧ:ММ.')
        cursor.execute('''INSERT INTO business_work_digest_settings(business_id,local_time,enabled) VALUES (%s,%s,%s)
            ON CONFLICT(business_id) DO UPDATE SET local_time=EXCLUDED.local_time,enabled=EXCLUDED.enabled''',(business,value,args.get('enabled') is not False))
    cursor.execute('SELECT local_time,enabled FROM business_work_digest_settings WHERE business_id=%s',(business,))
    row=_row(cursor,cursor.fetchone())
    return {'local_time':str(row.get('local_time') or '18:00')[:5],'enabled':row.get('enabled',True)}
