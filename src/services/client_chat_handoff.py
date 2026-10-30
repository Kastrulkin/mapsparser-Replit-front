"""Durable internal handoff using existing conversations/messages; no provider sends."""
import json
import uuid
from database_manager import DatabaseManager
from services.business_permissions import require_permission


def _event(cursor, conversation_id, kind, payload):
    cursor.execute('''INSERT INTO aiagentmessages(id,conversation_id,message_type,content,sender)
        VALUES(%s,%s,%s,%s,'operator')''',
        (str(uuid.uuid4()),conversation_id,kind,json.dumps(payload,ensure_ascii=False)))


def enqueue(cursor, business_id, conversation_id, reason):
    cursor.execute('SELECT current_state FROM aiagentconversations WHERE id=%s AND business_id=%s FOR UPDATE',(conversation_id,business_id))
    row=cursor.fetchone()
    if not row:
        raise ValueError('Диалог не найден.')
    if row['current_state'] in {'waiting_for_staff','human_active'}:
        return row['current_state']
    cursor.execute("UPDATE aiagentconversations SET current_state='waiting_for_staff',is_agent_paused=1,last_message_at=NOW(),updated_at=NOW() WHERE id=%s",(conversation_id,))
    _event(cursor,conversation_id,'handoff_requested',{'reason':reason[:500],'delivery':'localos_inbox'})
    return 'waiting_for_staff'


def request_handoff(business_id, conversation_id, reason):
    db=DatabaseManager()
    try:
        state=enqueue(db.conn.cursor(),business_id,conversation_id,reason)
        db.conn.commit()
        return {'success':True,'state':state,'delivery':'localos_inbox','agent_paused':True}
    except Exception:
        db.conn.rollback()
        raise
    finally:db.close()


def operate(cursor, business_id, conversation_id, user, action):
    require_permission(cursor,business_id,user,'operations.write')
    cursor.execute('SELECT current_state FROM aiagentconversations WHERE id=%s AND business_id=%s FOR UPDATE',(conversation_id,business_id))
    row=cursor.fetchone()
    if not row:raise ValueError('Диалог не найден.')
    current=row['current_state']
    if action=='accept':
        if current=='human_active':
            cursor.execute("SELECT content FROM aiagentmessages WHERE conversation_id=%s AND message_type='handoff_accept' ORDER BY created_at DESC LIMIT 1",(conversation_id,))
            existing=cursor.fetchone()
            if existing and json.loads(existing['content']).get('actor')==user['user_id']:
                return {'state':current,'is_agent_paused':1,'conversation_id':conversation_id}
        if current!='waiting_for_staff':raise ValueError('Диалог уже принят или не ожидает сотрудника.')
        state='human_active'
    elif action in {'close','reply'}:
        if current!='human_active':raise ValueError('Сначала примите диалог.')
        cursor.execute("SELECT content FROM aiagentmessages WHERE conversation_id=%s AND message_type='handoff_accept' ORDER BY created_at DESC LIMIT 1",(conversation_id,))
        accepted=cursor.fetchone()
        actor=json.loads(accepted['content']).get('actor') if accepted else None
        if actor!=user['user_id'] and not user.get('is_superadmin'):
            raise PermissionError('Диалог принят другим сотрудником.')
        state='closing' if action=='close' else 'human_active'
    else:raise ValueError('Неизвестное действие.')
    cursor.execute('UPDATE aiagentconversations SET current_state=%s,is_agent_paused=1,updated_at=NOW() WHERE id=%s',(state,conversation_id))
    _event(cursor,conversation_id,'handoff_'+action,{'actor':user['user_id'],'from':current,'to':state})
    return {'state':state,'is_agent_paused':1,'conversation_id':conversation_id}
