"""Explicit self-only notification pilot for synthetic client handoffs.

Reuses LocalOS owner-bot transport. No background dispatch or staff subscription.
A persisted sending claim prevents a duplicate after timeout or process failure.
"""
import json
import uuid
from urllib.parse import urlencode
from database_manager import DatabaseManager
from services.business_permissions import require_permission
from services.telegram_bot_sender import send_telegram_message_result


def dialogue_url(business_id, conversation_id):
    return 'https://localos.pro/dashboard/agents?' + urlencode({
        'section':'clients','view':'handoffs','business_id':business_id,
        'scope_type':'business','conversation_id':conversation_id})


def mini_app_url(business_id, conversation_id):
    return 'https://localos.pro/telegram/control?' + urlencode({'screen':'client_handoffs','scope_type':'business','scope_id':business_id,'item_type':'client_conversation','item_id':conversation_id})

def notification_markup(business_id, conversation_id):
    return {'inline_keyboard':[[{'text':'Открыть диалог LocalOS','web_app':{'url':mini_app_url(business_id,conversation_id)}}]]}


def notify_self(business_id, conversation_id, user):
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor()
        require_permission(cursor,business_id,user,'operations.write')
        cursor.execute('SELECT client_phone,current_state FROM aiagentconversations WHERE id=%s AND business_id=%s FOR UPDATE',(conversation_id,business_id))
        conversation=cursor.fetchone()
        if not conversation or not str(conversation['client_phone']).startswith('test-handoff:'):
            raise ValueError('Тестовое уведомление доступно только во внутреннем тестовом диалоге.')
        if conversation['current_state']!='waiting_for_staff':
            raise ValueError('Диалог уже принят или не ожидает сотрудника.')
        cursor.execute('''SELECT p.telegram_id,u.is_active FROM telegramcontrolpreferences p
            JOIN users u ON u.id=p.user_id WHERE p.user_id=%s''',(user['user_id'],))
        recipient=cursor.fetchone()
        if not recipient or not recipient['is_active'] or not recipient['telegram_id'] or int(recipient['telegram_id'])<=0:
            raise ValueError('Подключите личный Telegram к своему аккаунту LocalOS.')
        cursor.execute("SELECT content FROM aiagentmessages WHERE conversation_id=%s AND message_type='handoff_notification' ORDER BY created_at DESC",(conversation_id,))
        for row in cursor.fetchall():
            receipt=json.loads(row['content'])
            if receipt.get('actor')==user['user_id'] and receipt.get('status') in {'sending','sent','unknown'}:
                db.conn.commit()
                return {**receipt,'duplicate_prevented':True}
        cursor.execute('SELECT name FROM businesses WHERE id=%s',(business_id,))
        business=cursor.fetchone()
        identifier=str(uuid.uuid4());url=dialogue_url(business_id,conversation_id)
        receipt={'actor':user['user_id'],'recipient_user_id':user['user_id'],'channel':'telegram',
                 'status':'sending','test_only':True,'url':url,'mini_app_url':mini_app_url(business_id,conversation_id),'message_id':None}
        cursor.execute("INSERT INTO aiagentmessages(id,conversation_id,message_type,content,sender) VALUES(%s,%s,'handoff_notification',%s,'operator')",(identifier,conversation_id,json.dumps(receipt,ensure_ascii=False)))
        db.conn.commit()
        # No customer transcript, phone or health information leaves LocalOS.
        text=f"Тест LocalOS — {business['name']}\nВнутренний тестовый диалог ожидает принятия.\nОткройте обращение и нажмите «Взять диалог». Это проверка для вас; сотрудникам уведомление не отправлялось. Автоответы выключены."
        result=send_telegram_message_result(str(recipient['telegram_id']),text,
            notification_markup(business_id,conversation_id),include_outcome=True)
        outcome=result.get('publish_outcome')
        receipt.update(status='sent' if outcome=='confirmed' and result.get('message_id') else ('failed' if outcome in {'rejected','not_attempted'} else 'unknown'),
                       message_id=result.get('message_id') or None,reason_code=result.get('reason_code') or '',
                       evidence_kind='provider_observed' if outcome=='confirmed' else 'provider_attempt',
                       delivery_note='Telegram подтвердил отправку; прочтение не подтверждено.' if outcome=='confirmed' else 'Результат отправки требует проверки.')
        cursor.execute('UPDATE aiagentmessages SET content=%s WHERE id=%s',(json.dumps(receipt,ensure_ascii=False),identifier))
        db.conn.commit()
        return receipt
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
