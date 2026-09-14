"""Versioned replacement of unpublished plan slots through the existing approval."""
import json
import re
import os
import hashlib
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from services.operator_conversations import _row
from services.operator_plan_continuation import PlanClarification


def enabled(business_id):
    return business_id in {value.strip() for value in os.getenv('OPERATOR_PLAN_REVISION_ASYNC_BUSINESS_IDS','').split(',') if value.strip()}


def prepare(cursor, business_id, user_id, message, args, queue=False, generation_cache=None):
    from services import operator_editorial, business_input_settings, content_plan_direction
    operator_editorial.authorize_actor(cursor, user_id, business_id)
    plan_id = args.get('plan_id')
    if not plan_id:
        selector=args.get('selector') or ('today' if re.search(r'создан.{0,15}сегодня|сегодня.{0,15}создан',message,re.I) else 'current' if re.search(r'текущ',message,re.I) else 'latest')
        clause='';params=[business_id]
        if selector in {'today','current'}:
            zone=business_input_settings.resolve(cursor,business_id).get('timezone')
            if not zone:raise PlanClarification('Для выбора плана по местной дате укажите часовой пояс или конкретный план.')
            today=datetime.now(ZoneInfo(zone)).date()
            clause=' AND (created_at AT TIME ZONE %s)::date=%s' if selector=='today' else ' AND period_start<=%s AND period_end>=%s'
            params.extend([zone,today] if selector=='today' else [today,today])
        cursor.execute("SELECT id,title FROM contentplans WHERE business_id=%s AND plan_status<>'archived'"+clause+" ORDER BY created_at DESC,id DESC LIMIT 2",tuple(params))
        plans=[_row(cursor,row) for row in cursor.fetchall()]
        if not plans: raise PlanClarification('Нет подходящего плана для изменения. Укажите другой период или план.')
        if len(plans)>1 and selector!='latest':raise PlanClarification('Подходят несколько планов: '+', '.join(row['title'] for row in plans)+'. Какой изменить?')
        plan_id=plans[0]['id']
    cursor.execute('SELECT * FROM contentplans WHERE id=%s AND business_id=%s',(plan_id,business_id))
    plan=_row(cursor,cursor.fetchone())
    if not plan or plan['plan_status']=='archived':raise PlanClarification('Выберите действующий план.')
    cursor.execute('SELECT COUNT(*) n FROM contentplanitems WHERE plan_id=%s AND business_id=%s',(plan_id,business_id))
    if _row(cursor,cursor.fetchone())['n']>200:raise PlanClarification('План слишком большой для одной переработки. Выберите меньший период.')
    rows=operator_editorial._items(cursor,business_id,plan_id)
    editable=[row for row in rows if row['status'] in operator_editorial.EDITABLE]
    if not editable:raise PlanClarification('В плане нет неопубликованных постов для изменения.')
    count=args.get('post_count');interval=args.get('interval_days')
    if type(count)!=int or not 1<=count<=90 or type(interval)!=int or not 1<=interval<=90:
        raise PlanClarification('Укажите количество постов и интервал между ними.')
    zone=business_input_settings.resolve(cursor,business_id).get('timezone')
    if not zone:raise PlanClarification('Для назначения дат укажите часовой пояс бизнеса.')
    start=max(date.fromisoformat(str(plan['period_start'])[:10]),datetime.now(ZoneInfo(zone)).date())
    if args.get('start_date'):start=max(start,date.fromisoformat(args['start_date']))
    dates=[start+timedelta(days=index*interval) for index in range(count)]
    end=date.fromisoformat(str(plan['period_end'])[:10])
    if dates[-1]>end and not args.get('extend_period'):
        raise PlanClarification(f"Посты помещаются до {dates[-1]}, но план заканчивается {end}. Продлить период до этой даты?")
    if args.get('_expected_version') and str(plan['updated_at'])!=args['_expected_version']:
        raise PlanClarification('План изменился после постановки задачи. Повторите команду для актуального плана.')
    pilots={value.strip() for value in os.getenv('OPERATOR_PLAN_REVISION_ASYNC_BUSINESS_IDS','').split(',') if value.strip()}
    if queue and business_id in pilots:
        from services.operator_async_jobs import create_operator_async_job
        from services.operator_conversations import find_latest_operator_conversation
        conversation=find_latest_operator_conversation(cursor,business_id=business_id,user_id=user_id,channel=args['_channel'])
        job=create_operator_async_job(cursor,user_id=user_id,business_id=business_id,action_id=None,kind='content_plan_revision',
            payload={'message':message,'args':{**args,'plan_id':plan_id,'_expected_version':str(plan['updated_at'])},'conversation_id':conversation['id'],'channel':args['_channel']},
            idempotency_key='plan-revision:'+str(uuid.uuid4()),stage='Готовлю новые темы и даты',max_attempts=2)
        return operator_editorial._result('Готовлю изменения плана в фоне. Предпросмотр появится в этом диалоге; сам план пока не изменён.','queued',async_job_id=job['id'])
    cursor.execute('SELECT name,description FROM businesses WHERE id=%s',(business_id,))
    business=_row(cursor,cursor.fetchone())
    cursor.execute('SELECT name FROM userservices WHERE business_id=%s AND COALESCE(is_active,TRUE)=TRUE LIMIT 40',(business_id,))
    context={'business':business,'services':[_row(cursor,row) for row in cursor.fetchall()]}
    skeleton={'items':[{'scheduled_for':value.isoformat()} for value in dates],'meta':{}}
    cache_options={'generation_cache':generation_cache} if generation_cache else {}
    proposal=content_plan_direction.apply_direction(skeleton,context,message,business_id,user_id,**cache_options)
    changes=[]
    for index,item in enumerate(proposal['items']):
        changes.append({**item,'id':editable[index]['id'] if index<len(editable) else str(uuid.uuid4())})
    archived=[row['id'] for row in editable[count:]]
    envelope={'kind':'revision','business_id':business_id,'plan_id':plan_id,'plan_version':str(plan['updated_at']),
        'versions':{row['id']:operator_editorial._version(row) for row in rows},'changes':changes,
        'period_end':max(end,dates[-1]).isoformat(),'archive_ids':archived,'brief':message,'summary':proposal['meta']['editorial_summary']}
    text=f"Предлагаю переработать план.\nПериод: {plan['period_start']} — {envelope['period_end']}. Первая новая дата: {start}.\nАрхивировать прежних неопубликованных записей: {len(archived)}. Опубликованные посты остаются прежними.\nРаспределение: {envelope['summary']}. Подтвердите изменения.\n"
    text+='\n'.join(item['scheduled_for']+': '+item['theme'] for item in changes)
    return operator_editorial._result(text,'approval_required',approval={'envelope':envelope})


def apply(cursor,business_id,user_id,envelope):
    from services import operator_editorial
    operator_editorial.authorize_actor(cursor,user_id,business_id)
    if not enabled(business_id):return operator_editorial._result('Изменение плана временно отключено.','blocked')
    if envelope.get('business_id')!=business_id:return operator_editorial._result('Чужой план.','blocked')
    cursor.execute('SELECT * FROM contentplans WHERE id=%s AND business_id=%s FOR UPDATE',(envelope['plan_id'],business_id))
    plan=_row(cursor,cursor.fetchone())
    rows={row['id']:row for row in operator_editorial._items(cursor,business_id,envelope['plan_id'],lock=True)}
    if not plan or str(plan['updated_at'])!=envelope['plan_version'] or {key:operator_editorial._version(row) for key,row in rows.items()}!=envelope['versions']:
        return operator_editorial._result('План изменился после предпросмотра. Подготовьте изменения заново.','blocked')
    for item in envelope['changes']:
        if item['id'] in rows:
            operator_editorial._change(cursor,rows[item['id']],item['theme'],item['goal'],user_id,focus=envelope['brief'])
            cursor.execute('UPDATE contentplanitems SET scheduled_for=%s WHERE id=%s AND business_id=%s',(item['scheduled_for'],item['id'],business_id))
        else:
            cursor.execute("INSERT INTO contentplanitems(id,plan_id,business_id,theme,goal,scheduled_for,status,content_type,source_kind,metadata_json) VALUES (%s,%s,%s,%s,%s,%s,'planned','news','editorial_brief',%s::jsonb)",
                (item['id'],plan['id'],business_id,item['theme'],item['goal'],item['scheduled_for'],json.dumps({'editorial_brief':envelope['brief']})))
    for entry_id in envelope['archive_ids']:
        row=rows[entry_id]
        operator_editorial._change(cursor,row,row['theme'],row.get('goal') or '',user_id,focus=envelope['brief'])
        cursor.execute("UPDATE contentplanitems SET status='archived' WHERE id=%s AND business_id=%s",(entry_id,business_id))
    final_rows=operator_editorial._items(cursor,business_id,plan['id'])
    items=[{key:row.get(key) for key in ('id','theme','goal','scheduled_for','status','content_type')} for row in final_rows if row['status']!='archived']
    weekly={}
    for item in items:
        iso=date.fromisoformat(str(item['scheduled_for'])[:10]).isocalendar()
        weekly.setdefault(f'{iso.year}-W{iso.week:02d}',[]).append(item)
    cursor.execute("UPDATE contentplans SET period_end=%s,generated_plan_json=COALESCE(generated_plan_json,'{}'::jsonb)||%s::jsonb,updated_at=clock_timestamp() WHERE id=%s AND business_id=%s",
        (envelope['period_end'],json.dumps({'editorial_revision':envelope,'items':items,'weekly_groups':weekly},default=str,ensure_ascii=False),plan['id'],business_id))
    return operator_editorial._result(f"План изменён: {len(envelope['changes'])} постов. {envelope['summary']}. Предыдущие тексты сохранены в истории.",changed_count=len(envelope['changes']))


def process_job(claimed):
    from database_manager import DatabaseManager
    from services.content_plan_direction import PlanGenerationError
    from services.operator_conversations import append_operator_message,create_pending_operator_action
    from services.operator_audio import authorize_actor
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor();payload=claimed['payload_json'];business=claimed['business_id'];user=claimed['user_id']
        authorize_actor(cursor,user,business)
        if not enabled(business):raise ValueError('Подготовка изменений временно отключена.')
        cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('plan-preview:'+claimed['id'],))
        cursor.execute('SELECT payload_json FROM operator_async_jobs WHERE id=%s',(claimed['id'],))
        fresh_payload=_row(cursor,cursor.fetchone()).get('payload_json') or {}
        payload['generation_cache']=fresh_payload.get('generation_cache') or {}
        cursor.execute("SELECT result_json FROM operatormessages WHERE business_id=%s AND user_id=%s AND result_json->>'async_job_id'=%s AND status NOT IN ('queued','failed','cancelled') ORDER BY created_at DESC LIMIT 1",(business,user,claimed['id']))
        previous=_row(cursor,cursor.fetchone())
        if previous:return previous['result_json']
        def cache(prompt,value):
            key=hashlib.sha256(prompt.encode()).hexdigest()
            if value is None:return (payload.get('generation_cache') or {}).get(key)
            checkpoint=DatabaseManager()
            try:
                checkpoint.conn.cursor().execute("UPDATE operator_async_jobs SET payload_json=jsonb_set(payload_json,'{generation_cache}',COALESCE(payload_json->'generation_cache','{}'::jsonb)||%s::jsonb) WHERE id=%s AND user_id=%s AND business_id=%s",(json.dumps({key:value}),claimed['id'],user,business))
                checkpoint.conn.commit()
                payload.setdefault('generation_cache',{})[key]=value
            except Exception:
                checkpoint.conn.rollback();raise
            finally:checkpoint.close()
        try:result=prepare(cursor,business,user,payload['message'],payload['args'],generation_cache=cache)
        except PlanGenerationError:
            raise
        except PlanClarification:
            import sys
            result={'status':'clarification_required','chat_response':str(sys.exception())}
        authorize_actor(cursor,user,business)
        cursor.execute('SELECT status,lease_token FROM operator_async_jobs WHERE id=%s FOR UPDATE',(claimed['id'],))
        lease=_row(cursor,cursor.fetchone())
        if lease.get('status')=='cancelled' or (claimed.get('lease_token') and lease.get('lease_token')!=claimed['lease_token']):
            db.conn.rollback();return {'status':'cancelled','chat_response':'Подготовка отменена. План остался прежним.'}
        result.update(async_job_id=claimed['id'],conversation_id=payload['conversation_id'],capability='content.plan.refocus')
        if result['status']=='approval_required':
            action=create_pending_operator_action(cursor,conversation_id=payload['conversation_id'],business_id=business,user_id=user,capability='content.plan.refocus',envelope=result['approval']['envelope'],request_key='plan-preview:'+claimed['id'])
            result['approval'].update(action_id=action['id'],status='pending',summary=result['chat_response'])
            cursor.execute("UPDATE operatoractions SET status='rejected',updated_at=NOW() WHERE conversation_id=%s AND capability='content.plan.refocus' AND status='pending_approval' AND id<>%s AND created_at<%s",(payload['conversation_id'],action['id'],action['created_at']))
            cursor.execute("UPDATE operatoractions SET expires_at=COALESCE(expires_at,NOW()+INTERVAL '30 minutes') WHERE id=%s",(action['id'],))
        message_id=append_operator_message(cursor,conversation_id=payload['conversation_id'],business_id=business,user_id=user,role='operator',content=result['chat_response'],capability=result['capability'],status=result['status'],result=result)
        result['message_id']=message_id
        cursor.execute('UPDATE operatormessages SET result_json=%s::jsonb WHERE id=%s',(json.dumps(result,default=str),message_id))
        cursor.execute("UPDATE operator_chat_requests SET result_json=result_json||%s::jsonb WHERE business_id=%s AND user_id=%s AND result_json->>'async_job_id'=%s",(json.dumps(result,default=str),business,user,claimed['id']))
        db.conn.commit();return result
    except Exception:
        db.conn.rollback();raise
    finally:db.close()


def explicit_schedule(message):
    """Only resolve unambiguous arithmetic; prose topics remain with the generator."""
    if re.match(r'\s*(если|например|как|можно ли)\b',message,re.I):return None
    if not re.search(r'измен|переработ|помен|замен',message,re.I):return None
    if not re.search(r'(?:один|1)\s+пост\w*\s+в\s+недел|еженедель',message,re.I):return None
    numbers={'один':1,'одна':1,'два':2,'две':2,'три':3,'четыре':4,'пять':5,'шесть':6,'семь':7,'восемь':8,'девять':9,'десять':10}
    pattern=r'\b(\d+|'+'|'.join(numbers)+r')\s+(?:пост\w*\s+)?(?:про|о)\s+'
    matches=re.findall(pattern,message.lower())
    if not matches or re.search(r'остальн|часть|произвольн|прочие',message,re.I):return None
    count=sum(int(value) if value.isdecimal() else numbers[value] for value in matches)
    if not 1<=count<=90:return None
    return {'post_count':count,'interval_days':7,'extend_period':bool(re.search(r'\bпродл',message,re.I)) and not bool(re.search(r'\bне\s+продл',message,re.I))}


def record_failure(cursor,claimed):
    from services.operator_conversations import append_operator_message
    payload=claimed.get('payload_json') or {};conversation=payload.get('conversation_id')
    if not conversation:return
    business=claimed['business_id'];user=claimed['user_id']
    cursor.execute("SELECT id FROM operatormessages WHERE business_id=%s AND user_id=%s AND result_json->>'async_job_id'=%s AND status='failed' LIMIT 1",(business,user,claimed['id']))
    if cursor.fetchone():return
    result={'status':'failed','async_job_id':claimed['id'],'conversation_id':conversation,'capability':'content.plan.refocus','error_code':'plan_revision_failed','chat_response':'Не удалось подготовить изменения. Эта команда не изменила план. Повторите задание из списка задач.'}
    result['message_id']=append_operator_message(cursor,conversation_id=conversation,business_id=business,user_id=user,role='operator',content=result['chat_response'],capability=result['capability'],status='failed',result=result)
    cursor.execute('UPDATE operatormessages SET result_json=%s::jsonb WHERE id=%s',(json.dumps(result),result['message_id']))
    cursor.execute("UPDATE operator_chat_requests SET result_json=result_json||%s::jsonb WHERE business_id=%s AND user_id=%s AND result_json->>'async_job_id'=%s",(json.dumps(result),business,user,claimed['id']))
