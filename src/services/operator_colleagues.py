"""Single-recipient pilot messages using Operator approval, jobs and journey outbox."""
import hashlib
import json
import os
import uuid
import requests

from database_manager import DatabaseManager
from services.operator_conversations import _row
from services import operator_workday


def recipient(cursor,business):
    cursor.execute('''SELECT p.version,p.recipient_user_id,u.name,u.telegram_id,u.is_active,p.updated_by
        FROM operator_pilot_settings p JOIN users u ON u.id=p.recipient_user_id WHERE p.business_id=%s''',(business,))
    row=_row(cursor,cursor.fetchone())
    if not row or not row['is_active'] or not row.get('telegram_id'):
        raise ValueError('Владелец должен выбрать получателя с подключённым Telegram в настройках пилота.')
    # Recipients are either the configuring owner themself or a still-active member/owner.
    cursor.execute('''SELECT 1 FROM businesses b WHERE b.id=%s AND (b.owner_id=%s
        OR EXISTS(SELECT 1 FROM business_members m WHERE m.business_id=b.id AND m.user_id=%s AND m.status='active')
        OR EXISTS(SELECT 1 FROM users u WHERE u.id=%s AND u.id=%s AND u.is_superadmin=TRUE AND u.is_active=TRUE))''',
        (business,row['recipient_user_id'],row['recipient_user_id'],row['recipient_user_id'],row['updated_by']))
    if not cursor.fetchone():raise PermissionError('Получатель больше не имеет доступа к бизнесу.')
    return row


def prepare(cursor,business,user,args):
    operator_workday.authorize(cursor,business,user)
    selected=recipient(cursor,business)
    text=str(args.get('message') or '').strip()
    if not 1<=len(text)<=3000:raise ValueError('Сообщение должно содержать от 1 до 3000 символов.')
    snapshot=operator_workday.schedule(cursor,business,args['date'])
    if not snapshot or snapshot['version']!=args.get('schedule_version'):
        raise ValueError('Сначала проведите планёрку по актуальному расписанию.')
    preview=f"Тестовый получатель: {selected['name']}\n\n{text}\n\nПодтвердите отправку этому получателю."
    return {'status':'approval_required','capability':'work.colleague','chat_response':preview,
            'approval':{'summary':preview,'envelope':{'business_id':business,'date':args['date'],'schedule_version':snapshot['version'],
                'recipient_user_id':selected['recipient_user_id'],'recipient_version':selected['version'],
                'telegram_id':selected['telegram_id'],'message':text}}}


def enqueue(cursor,business,user,envelope,action_id):
    operator_workday.authorize(cursor,business,user)
    selected=recipient(cursor,business)
    snapshot=operator_workday.schedule(cursor,business,envelope['date'])
    if envelope.get('business_id')!=business or not snapshot or snapshot['version']!=envelope['schedule_version']:
        raise ValueError('Расписание изменилось. Подготовьте сообщение заново.')
    if any(envelope[key]!=selected[key] for key in ('recipient_user_id','telegram_id')) or envelope['recipient_version']!=selected['version']:
        raise ValueError('Получатель изменился. Подготовьте сообщение заново.')
    identifier=str(uuid.uuid5(uuid.NAMESPACE_URL,'operator-colleague:'+action_id))
    key=hashlib.sha256(('operator-colleague:'+action_id).encode()).hexdigest()
    cursor.execute('''INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,entity_id,action_type,title,description,
        cta_label,cta_target_json,payload_json,dedupe_key,due_at)
        VALUES (%s,%s,%s,'work_journal','operator_colleague',%s,'send_colleague','Сообщение по планёрке',%s,
        'Открыть планёрку','{}'::jsonb,%s::jsonb,%s,NOW()) ON CONFLICT(dedupe_key) DO NOTHING''',
        (identifier,business,selected['recipient_user_id'],action_id,envelope['message'],json.dumps(envelope),key))
    cursor.execute('''INSERT INTO journey_action_notification_deliveries(dedupe_key,action_id,action_version,user_id,telegram_id,message_text,reply_markup_json,dispatch_state)
        VALUES (%s,%s,1,%s,%s,%s,'{}'::jsonb,'queued') ON CONFLICT(dedupe_key) DO NOTHING''',
        (key,identifier,selected['recipient_user_id'],str(selected['telegram_id']),envelope['message']))
    from services.operator_async_jobs import create_operator_async_job
    job=create_operator_async_job(cursor,user_id=user,business_id=business,action_id=None,
        kind='operator_colleague_send',payload={'dedupe_key':key,'envelope':envelope},idempotency_key='colleague:'+action_id,stage='Отправляю подтверждённое сообщение',max_attempts=1)
    return {'status':'completed','capability':'work.colleague','chat_response':'Отправка подтверждена и поставлена в очередь. Доставка ещё не подтверждена.',
            'async_job_id':job['id'],'delivery_state':'queued','provider_write_performed':False}


def process_job(job):
    db=DatabaseManager()
    try:
        c=db.conn.cursor();business=job['business_id'];payload=job['payload_json'];envelope=payload['envelope']
        operator_workday.authorize(c,business,job['user_id'])
        selected=recipient(c,business)
        if selected['version']!=envelope['recipient_version'] or selected['telegram_id']!=envelope['telegram_id']:
            raise ValueError('Получатель изменился; отправка остановлена.')
        snapshot=operator_workday.schedule(c,business,envelope['date'])
        if not snapshot or snapshot['version']!=envelope['schedule_version']:
            raise ValueError('Расписание изменилось; отправка остановлена.')
        c.execute('SELECT * FROM journey_action_notification_deliveries WHERE dedupe_key=%s FOR UPDATE',(payload['dedupe_key'],))
        row=_row(c,c.fetchone())
        if row.get('sent_at'):
            return {'status':'completed','chat_response':'Сообщение отправлено.','provider_message_id':row.get('provider_message_id')}
        if row.get('attempted_at'):
            return {'status':'blocked','chat_response':'Результат предыдущей отправки неизвестен. Проверьте чат; автоматического повтора не будет.','delivery_state':'unknown'}
        token=os.getenv('TELEGRAM_BOT_TOKEN') or ''
        if not token:raise ValueError('Telegram-бот не настроен.')
        c.execute("UPDATE journey_action_notification_deliveries SET attempted_at=NOW(),dispatch_state='unknown' WHERE dedupe_key=%s",(payload['dedupe_key'],))
        db.conn.commit()  # Persist the no-blind-retry fence before network I/O.
        response=requests.post('https://api.telegram.org/bot'+token+'/sendMessage',json={'chat_id':str(selected['telegram_id']),'text':row['message_text']},timeout=(10,30))
        body=response.json()
        if response.status_code!=200 or not body.get('ok'):
            c.execute("UPDATE journey_action_notification_deliveries SET dispatch_state='failed' WHERE dedupe_key=%s",(payload['dedupe_key'],))
            db.conn.commit()
            return {'status':'blocked','chat_response':'Telegram отклонил отправку. Проверьте подключение получателя.','delivery_state':'failed'}
        message_id=str(body['result']['message_id'])
        c.execute("UPDATE journey_action_notification_deliveries SET sent_at=NOW(),dispatch_state='sent',provider_message_id=%s WHERE dedupe_key=%s",(message_id,payload['dedupe_key']))
        db.conn.commit()
        return {'status':'completed','chat_response':'Сообщение отправлено выбранному получателю.','provider_message_id':message_id,'delivery_state':'sent'}
    except requests.RequestException:
        return {'status':'blocked','chat_response':'Результат отправки неизвестен. Проверьте чат; автоматического повтора не будет.','delivery_state':'unknown'}
    finally:
        db.close()


def handle(envelope,user_data):
    from services.agent_capability_handlers import _actor_user_id
    db=DatabaseManager()
    try:
        value=enqueue(db.conn.cursor(),envelope['tenant_id'],_actor_user_id(envelope,user_data),envelope['payload'],envelope['action_id'])
        db.conn.commit()
        return value
    finally:
        db.close()


def tools(cursor,business,user,channel='web',orchestrator=None):
    def approval(args):
        preview=prepare(cursor,business,user,args)
        from services.operator_core import _prepare_registered_capability_approval
        fingerprint=hashlib.sha256(json.dumps(preview['approval']['envelope'],sort_keys=True).encode()).hexdigest()
        prepared=_prepare_registered_capability_approval(capability='work.colleague',tool_name='work.prepare_colleague_message',
            business_id=business,user_id=user,channel=channel,message=preview['chat_response']+'\n'+fingerprint,
            payload=preview['approval']['envelope'],backend_capability='work.colleague.send',orchestrator=orchestrator)
        if prepared.get('status')=='approval_required':
            prepared['chat_response']=preview['chat_response']
            prepared['approval']['summary']=preview['chat_response']
        return prepared
    return [{'name':'work.prepare_colleague_message','title':'Сообщение по планёрке','capability':'work.colleague',
        'risk_class':'external_send_request','approval_required':True,
        'description':'Подготовить сообщение по проверенной планёрке единственному выбранному владельцем получателю. Никаких клиентских рассылок. date и schedule_version из morning_briefing. Не утверждать отправку до подтверждения результата.',
        'input_schema':{'type':'object','required':['date','schedule_version','message'],'properties':{'date':{'type':'string'},'schedule_version':{'type':'integer'},'message':{'type':'string'}}},
        'prepare_approval':approval}]
