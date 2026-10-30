"""Account-restricted Raschyoska manual Telegram pilot. Never invokes AI."""
import hashlib
import json
import uuid
from database_manager import DatabaseManager
from services.business_permissions import load_actor
from services.client_chat_handoff import enqueue, operate
from services.telegram_bot_sender import send_telegram_message_result

BUSINESS = '0f67ac22-132f-41e7-b473-667c46f364fa'
ACTOR = 'a453a8b3-3b26-4c4e-81e3-1b973d4b8755'
PREFIX = 'tg-ras-pilot:'


def identity(cursor, telegram_id=None):
    cursor.execute("""SELECT u.telegram_id FROM users u JOIN telegramcontrolpreferences p ON p.user_id=u.id
        WHERE u.id=%s AND u.is_active=TRUE AND u.telegram_id=p.telegram_id""",(ACTOR,))
    row=cursor.fetchone()
    if not row or not row['telegram_id'] or int(row['telegram_id'])<=0:
        raise PermissionError('Тестовый Telegram не привязан.')
    target=str(row['telegram_id'])
    if telegram_id is not None and target!=str(telegram_id):
        raise PermissionError('Режим доступен только тестовому аккаунту.')
    return target


def is_pilot(business_id, phone):
    return business_id==BUSINESS and phone==PREFIX+ACTOR


def receive(telegram_id, message_id, text, command=None):
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor()
        identity(cursor,telegram_id)
        cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(PREFIX+ACTOR,))
        cursor.execute('SELECT id,current_state FROM aiagentconversations WHERE business_id=%s AND client_phone=%s ORDER BY created_at DESC LIMIT 1 FOR UPDATE',(BUSINESS,PREFIX+ACTOR))
        conversation=cursor.fetchone()
        if command=='start':
            if conversation and conversation['current_state']!='closing':
                raise ValueError('Сначала завершите текущее обращение или используйте /ras_exit.')
            cid=str(uuid.uuid4())
            cursor.execute("INSERT INTO aiagentconversations(id,business_id,client_phone,client_name,current_state,conversation_history,is_agent_paused) VALUES(%s,%s,%s,%s,'greeting','[]',1)",(cid,BUSINESS,PREFIX+ACTOR,'Клиент Расчёски — личный тест'))
            cursor.execute("INSERT INTO aiagentmessages(id,conversation_id,message_type,content,sender) VALUES(%s,%s,'client_pilot_mode','active','operator')",(str(uuid.uuid4()),cid))
            db.conn.commit()
            return {'handled':True,'notice':'Режим «Клиент Расчёски» включён только для вас. Напишите пожелание: передам сотруднику. ИИ не отвечает. Выход — /ras_exit.'}
        if not conversation:
            return {'handled':False}
        cid=conversation['id']
        cursor.execute("SELECT content FROM aiagentmessages WHERE conversation_id=%s AND message_type='client_pilot_mode' ORDER BY created_at DESC LIMIT 1",(cid,))
        mode=cursor.fetchone()
        if not mode or mode['content']!='active':return {'handled':False}
        if command=='exit':
            cursor.execute("INSERT INTO aiagentmessages(id,conversation_id,message_type,content,sender) VALUES(%s,%s,'client_pilot_mode','inactive','operator')",(str(uuid.uuid4()),cid))
            db.conn.commit()
            return {'handled':True,'notice':'Режим клиента выключен. Вы снова в чате с Оператором LocalOS.'}
        mid=str(uuid.uuid5(uuid.NAMESPACE_URL,'localos:ras-pilot:'+str(telegram_id)+':'+str(message_id)))
        cursor.execute("INSERT INTO aiagentmessages(id,conversation_id,message_type,content,sender) VALUES(%s,%s,'text',%s,'client') ON CONFLICT(id) DO NOTHING RETURNING id",(mid,cid,text[:4000]))
        inserted=cursor.fetchone()
        if not inserted:return {'handled':True}
        notify=conversation['current_state']=='greeting'
        if notify:enqueue(cursor,BUSINESS,cid,'Реальное сообщение разрешённого тестового клиента в Telegram')
        cursor.execute('UPDATE aiagentconversations SET last_message_at=NOW(),updated_at=NOW() WHERE id=%s',(cid,))
        actor=load_actor(cursor,ACTOR)
        db.conn.commit()
        if notify:
            from services.client_handoff_notifications import notify_self
            notify_self(BUSINESS,cid,actor)
        return {'handled':True}
    except Exception:
        db.conn.rollback()
        raise
    finally:db.close()


def reply(business_id, conversation_id, user, message):
    if not message or len(message)>4000:raise ValueError('Введите сообщение до 4000 символов.')
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor()
        target=identity(cursor)
        cursor.execute('SELECT client_phone FROM aiagentconversations WHERE id=%s AND business_id=%s FOR UPDATE',(conversation_id,business_id))
        row=cursor.fetchone()
        if not row or not is_pilot(business_id,row['client_phone']):
            raise ValueError('Клиентский канал не подключён.')
        # A durable claim suppresses retries after timeout, restart or a double click.
        key=str(uuid.uuid5(uuid.NAMESPACE_URL,'localos:ras-reply:'+conversation_id+':'+hashlib.sha256(message.encode()).hexdigest()))
        cursor.execute('SELECT content FROM aiagentmessages WHERE id=%s',(key,))
        previous=cursor.fetchone()
        if previous:
            from services.business_permissions import require_permission
            require_permission(cursor,business_id,user,'operations.write')
            receipt=json.loads(previous['content'])
            if receipt['status']!='sent':raise ValueError('Отправка уже выполнялась; проверьте Telegram. Повтор заблокирован.')
            return {'state':'human_active','delivery':'telegram','duplicate_prevented':True}
        result=operate(cursor,business_id,conversation_id,user,'reply')
        receipt={'status':'sending','actor':user['user_id']}
        cursor.execute("INSERT INTO aiagentmessages(id,conversation_id,message_type,content,sender) VALUES(%s,%s,'client_delivery',%s,'operator')",(key,conversation_id,json.dumps(receipt)))
        db.conn.commit()
        sent=send_telegram_message_result(target,'Расчёска · Ответ сотрудника\n'+message,include_outcome=True)
        confirmed=sent.get('publish_outcome')=='confirmed' and sent.get('message_id')
        receipt.update(status='sent' if confirmed else 'unknown',message_id=sent.get('message_id'),outcome=sent.get('publish_outcome'))
        cursor.execute('UPDATE aiagentmessages SET content=%s WHERE id=%s',(json.dumps(receipt),key))
        if confirmed:
            cursor.execute("INSERT INTO aiagentmessages(id,conversation_id,message_type,content,sender) VALUES(%s,%s,'text',%s,'operator')",(str(uuid.uuid4()),conversation_id,message))
        db.conn.commit()
        if not confirmed:raise ValueError('Доставка не подтверждена. Проверьте Telegram; автоматического повтора нет.')
        return {**result,'delivery':'telegram','external_dispatch_performed':True}
    except Exception:
        db.conn.rollback()
        raise
    finally:db.close()


async def handle(update, context, command=None):
    from services.owner_bot_context import owner_bot_platform
    if owner_bot_platform()!='telegram' or not update.message or update.effective_chat.type!='private':return False
    try:
        result=receive(str(update.effective_user.id),update.message.message_id,update.message.text or '',command)
    except PermissionError:
        if command:await update.message.reply_text('Режим недоступен этому аккаунту.')
        return bool(command)
    except ValueError as error:
        await update.message.reply_text(str(error))
        return True
    if result.get('notice'):await update.message.reply_text(result['notice'])
    return result['handled']


async def start(update, context):
    await handle(update,context,'start')


async def exit_mode(update, context):
    await handle(update,context,'exit')
