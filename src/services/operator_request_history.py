"""Durable receipts in the existing audit ledger, independent of command rollback.

The receipt never retries a business action. Its completed state is written in
the same transaction as the conversation result. Unfinished receipts remain
visible after a process restart.
"""
import hashlib
import json
import os
import uuid

from database_manager import DatabaseManager
from services.operator_conversations import _row

EVENT = 'operator_request_received'

REQUESTS_SQL = '''WITH requests AS (
    SELECT id,business_id,action_type,input_summary,output_summary,status,reason_code,metadata_json,created_at
    FROM agent_action_ledger WHERE action_type='operator_request_received'
    UNION ALL
    SELECT 'audio:' || a.id,a.business_id,'operator_request_received',
        COALESCE(NULLIF(a.transcript,''),'Голосовая запись'),
        CASE WHEN j.status='failed' THEN 'Не удалось распознать запись. Отправьте текст или новую запись.' ELSE '' END,
        CASE WHEN j.status='failed' THEN 'failed' WHEN a.status='cancelled' THEN 'cancelled' ELSE 'received' END,
        CASE WHEN j.status='failed' THEN 'stt' ELSE NULL END,
        jsonb_build_object('operator_user_id',a.user_id,'operator_channel',a.channel,'input_type','voice',
            'transcription_id',a.id,'audio_status',a.status,'job_id',a.job_id),a.created_at
    FROM operator_audio_assets a LEFT JOIN operator_async_jobs j ON j.id=a.job_id
    WHERE a.kind='transcription' AND NOT EXISTS (
        SELECT 1 FROM agent_action_ledger r WHERE r.action_type='operator_request_received'
        AND r.business_id=a.business_id AND r.metadata_json->>'transcription_id'=a.id)
    AND NOT EXISTS (SELECT 1 FROM operatormessages m WHERE m.business_id=a.business_id
        AND m.role='user' AND m.result_json->>'transcription_id'=a.id)
    UNION ALL
    SELECT 'message:' || m.id,m.business_id,'operator_request_received',m.content,'','history',NULL,
        jsonb_build_object('operator_user_id',m.user_id,'operator_channel',c.channel,
            'input_type',COALESCE(m.result_json->>'input_type','text'),
            'input_origin',m.result_json->>'input_origin',
            'transcription_id',m.result_json->>'transcription_id','conversation_id',m.conversation_id),m.created_at
    FROM operatormessages m JOIN operatorconversations c ON c.id=m.conversation_id
    WHERE m.role='user' AND NOT EXISTS (SELECT 1 FROM agent_action_ledger r
        WHERE r.action_type='operator_request_received' AND r.business_id=m.business_id
        AND r.metadata_json->>'user_message_id'=m.id)
) '''


def enabled(business_id):
    return business_id in os.getenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', '').split(',')


def scope(cursor, business_id, user_id):
    from core.auth_helpers import verify_business_access
    cursor.execute('SELECT id,is_active,is_superadmin FROM users WHERE id=%s', (user_id,))
    user = _row(cursor, cursor.fetchone())
    if not user or not user.get('is_active'):
        raise PermissionError('Аккаунт недоступен')
    allowed, owner = verify_business_access(cursor, business_id, user)
    if not allowed:
        raise PermissionError('Нет доступа к бизнесу')
    return bool(user.get('is_superadmin')) or owner == user_id


def receive(business_id, user_id, channel, message, payload, input_origin='user'):
    if channel not in {'web', 'telegram', 'telegram_mini_app'}:
        raise ValueError('Неизвестный канал')
    if not isinstance(message, str) or not message.strip() or len(message) > 10000:
        raise ValueError('Проверьте длину команды')
    request_id = str(payload.get('request_id') or uuid.uuid4())
    if len(request_id) > 200:
        raise ValueError('Проверьте идентификатор запроса')
    receipt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps([business_id, user_id, channel, request_id])))
    digest = hashlib.sha256(json.dumps([message, payload.get('transcription_id'), payload.get('url'),
        payload.get('input_context'), payload.get('work_change_hash')], ensure_ascii=False).encode()).hexdigest()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        from services.operator_audio import authorize_actor
        authorize_actor(cursor, user_id, business_id)
        if payload.get('conversation_id'):
            cursor.execute('SELECT id FROM operatorconversations WHERE id=%s AND business_id=%s AND user_id=%s AND channel=%s',
                           (payload['conversation_id'], business_id, user_id, channel))
            if not cursor.fetchone():
                raise PermissionError('Диалог недоступен')
        if payload.get('transcription_id'):
            cursor.execute('SELECT id FROM operator_audio_assets WHERE id=%s AND user_id=%s AND business_id=%s AND channel=%s',
                           (payload['transcription_id'], user_id, business_id, channel))
            if not cursor.fetchone():
                raise PermissionError('Запись недоступна')
        metadata = {'operator_user_id': user_id, 'operator_channel': channel, 'request_id': request_id,
                    'input_origin': input_origin,
                    'input_hash': digest, 'input_type': 'voice' if payload.get('transcription_id') else 'text',
                    'transcription_id': payload.get('transcription_id'), 'duplicates': 0}
        cursor.execute('''INSERT INTO agent_action_ledger
            (id,business_id,action_type,capability,risk_level,input_summary,status,metadata_json)
            VALUES (%s,%s,%s,'localos.operator','low',%s,'received',%s::jsonb)
            ON CONFLICT (id) DO UPDATE SET metadata_json=jsonb_set(agent_action_ledger.metadata_json,
                '{duplicates}',to_jsonb(COALESCE((agent_action_ledger.metadata_json->>'duplicates')::integer,0)+1))
            WHERE agent_action_ledger.metadata_json->>'input_hash'=EXCLUDED.metadata_json->>'input_hash'
            RETURNING id''', (receipt_id, business_id, EVENT, message, json.dumps(metadata)))
        if not cursor.fetchone():
            raise ValueError('Идентификатор запроса уже использован для другого текста')
        db.conn.commit()
        return receipt_id
    finally:
        db.conn.rollback()
        db.close()


def complete(cursor, receipt_id, result):
    metadata = {key: result.get(key) for key in ('message_id', 'user_message_id', 'conversation_id', 'capability', 'input_type')}
    cursor.execute('''UPDATE agent_action_ledger SET status=%s,output_summary=%s,
        metadata_json=metadata_json || %s::jsonb WHERE id=%s AND action_type=%s''',
        (result.get('status') or 'unknown', result.get('chat_response') or result.get('summary') or '',
         json.dumps(metadata, default=str), receipt_id, EVENT))


def fail(receipt_id, category):
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("UPDATE agent_action_ledger SET status='failed',reason_code=%s WHERE id=%s AND action_type=%s AND status='received'",
                       (category, receipt_id, EVENT))
        db.conn.commit()
    finally:
        db.conn.rollback()
        db.close()


def list_requests(cursor, business_id, user_id, filters):
    owner = scope(cursor, business_id, user_id)
    conditions = ['business_id=%s', 'action_type=%s']
    values = [business_id, EVENT]
    if not owner:
        conditions.append("metadata_json->>'operator_user_id'=%s")
        values.append(user_id)
    for parameter, expression in [('channel', "metadata_json->>'operator_channel'"),
                                 ('input_type', "metadata_json->>'input_type'"),
                                 ('user_id', "metadata_json->>'operator_user_id'"), ('status', 'status')]:
        if filters.get(parameter):
            conditions.append(expression + '=%s')
            values.append(filters[parameter])
    for key, comparison in [('from', '>='), ('until', '<')]:
        if filters.get(key):
            from datetime import datetime
            datetime.fromisoformat(filters[key])
            conditions.append('created_at' + comparison + '%s::timestamptz')
            values.append(filters[key])
    offset = max(0, min(int(filters.get('offset') or 0), 100000))
    cursor.execute(REQUESTS_SQL + 'SELECT id,input_summary,output_summary,status,reason_code,metadata_json,created_at FROM requests WHERE '
                   + ' AND '.join(conditions) + ' ORDER BY created_at DESC,id DESC LIMIT 51 OFFSET %s', (*values, offset))
    rows = [_row(cursor, row) for row in cursor.fetchall()]
    people = []
    if owner:
        cursor.execute(REQUESTS_SQL + '''SELECT DISTINCT u.id,COALESCE(to_jsonb(u)->>'name','Сотрудник') name
            FROM requests r JOIN users u ON u.id=r.metadata_json->>'operator_user_id'
            WHERE r.business_id=%s ORDER BY name,u.id LIMIT 200''', (business_id,))
        people = [_row(cursor, row) for row in cursor.fetchall()]
    return {'items': rows[:50], 'next_offset': offset + 50 if len(rows) > 50 else None, 'can_view_team': owner, 'people': people}


def detail(cursor, business_id, user_id, receipt_id):
    owner = scope(cursor, business_id, user_id)
    cursor.execute(REQUESTS_SQL + 'SELECT * FROM requests WHERE id=%s AND business_id=%s AND action_type=%s',
                   (receipt_id, business_id, EVENT))
    row = _row(cursor, cursor.fetchone())
    metadata = row.get('metadata_json') or {}
    if not row or (not owner and metadata.get('operator_user_id') != user_id):
        raise PermissionError('Обращение недоступно')
    cursor.execute('SELECT content,result_json FROM operatormessages WHERE id=%s AND business_id=%s AND user_id=%s',
                   (metadata.get('message_id'), business_id, metadata.get('operator_user_id')))
    row['response'] = _row(cursor, cursor.fetchone())
    cursor.execute('SELECT transcript,corrected_text,status FROM operator_audio_assets WHERE id=%s AND business_id=%s AND user_id=%s',
                   (metadata.get('transcription_id'), business_id, metadata.get('operator_user_id')))
    row['audio'] = _row(cursor, cursor.fetchone())
    cursor.execute("SELECT CASE WHEN j.status='failed' THEN 'failed' ELSE a.status END status,a.metadata_json->>'delivery' delivery FROM operator_audio_assets a LEFT JOIN operator_async_jobs j ON j.id=a.job_id WHERE a.message_id=%s AND a.business_id=%s AND a.user_id=%s AND a.kind='speech' ORDER BY a.created_at DESC LIMIT 1",
                   (metadata.get('message_id'), business_id, metadata.get('operator_user_id')))
    row['speech'] = _row(cursor, cursor.fetchone())
    cursor.execute("SELECT input_summary,created_at FROM agent_action_ledger WHERE business_id=%s AND action_type='operator_request_feedback' AND metadata_json->>'receipt_id'=%s ORDER BY created_at DESC",
                   (business_id, receipt_id))
    row['feedback'] = [_row(cursor, item) for item in cursor.fetchall()]
    return row


def action_finished(cursor, action_id, status, result):
    if not os.getenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS'):
        return
    cursor.execute('''UPDATE agent_action_ledger r SET status=%s,output_summary=%s,
        metadata_json=r.metadata_json || %s::jsonb FROM operatormessages m
        WHERE r.action_type=%s AND r.metadata_json->>'message_id'=m.id
        AND m.business_id=r.business_id AND m.result_json #>> '{approval,action_id}'=%s''',
        (status, result.get('chat_response') or '', json.dumps({'action_id': action_id}), EVENT, action_id))


def mark_delivery(receipt_id, status):
    if not receipt_id:
        return
    db = DatabaseManager()
    try:
        db.conn.cursor().execute('UPDATE agent_action_ledger SET metadata_json=metadata_json || %s::jsonb WHERE id=%s AND action_type=%s',
                                 (json.dumps({'delivery': status}), receipt_id, EVENT))
        db.conn.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).warning('operator_delivery_audit_unavailable')
    finally:
        db.conn.rollback()
        db.close()


def feedback(cursor, business_id, user_id, receipt_id, comment):
    detail(cursor, business_id, user_id, receipt_id)
    if not isinstance(comment, str) or not comment.strip() or len(comment) > 2000:
        raise ValueError('Опишите ошибку: до 2 000 символов')
    entry_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'operator-feedback:' + receipt_id + ':' + user_id))
    cursor.execute('''INSERT INTO agent_action_ledger
        (id,business_id,action_type,capability,risk_level,input_summary,status,metadata_json)
        VALUES (%s,%s,'operator_request_feedback','localos.operator','low',%s,'recorded',%s::jsonb)
        ON CONFLICT (id) DO UPDATE SET input_summary=EXCLUDED.input_summary''',
        (entry_id, business_id, comment.strip(), json.dumps({'receipt_id': receipt_id, 'operator_user_id': user_id})))
    return {'status': 'recorded', 'id': entry_id}
