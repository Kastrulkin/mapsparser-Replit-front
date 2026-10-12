"""Owner-facing outreach outcomes and delivery checkpoints in the existing ledger."""
from __future__ import annotations
import asyncio
import hashlib
import json
import uuid
from psycopg2.extras import Json

EVENT = 'operator_outreach_result'


def split_telegram_text(text, limit=3500):
    chunks, chunk, size = [], [], 0
    for character in str(text):
        width = len(character.encode('utf-16-le')) // 2
        if size + width > limit:
            chunks.append(''.join(chunk));chunk=[];size=0
        chunk.append(character);size += width
    if chunk: chunks.append(''.join(chunk))
    return chunks or ['Результат сохранён.']


def letters(cursor, task):
    ids = [str(value['campaign_id']) for value in (task.get('state', {}).get('campaign_results') or {}).values() if value.get('campaign_id')]
    if not ids: return []
    cursor.execute('''SELECT t.id,t.campaign_id,t.subject,t.generated_text,t.status,t.updated_at,
        t.message_brief_json,cp.normalized_value AS recipient,s.sender_identity AS sender
        FROM outreach_campaign_touches t JOIN outreach_campaigns c ON c.id=t.campaign_id
        LEFT JOIN lead_contact_points cp ON cp.id=t.contact_point_id
        LEFT JOIN outreach_sender_accounts s ON s.id=t.sender_account_id
        WHERE c.business_id=%s AND c.id::text=ANY(%s::text[]) AND t.sequence_index=0
        ORDER BY c.created_at,c.id''', (task['business_id'], ids))
    return [dict(row) for row in cursor.fetchall()]


def result(cursor, row):
    from services.outreach_continuation import view
    task = view(row); report = task['report']; drafts = letters(cursor, task)
    lines = [task['display_name'], task['presentation']['label'],
        f"Найдено: {report['found']}. Подходят: {report['eligible']} / {report.get('target') or 'не задана'}. Писем: {report['prepared']}.",
        f"Списано за выполнение: {report['credits_charged']} кр."]
    if row.get('stage'): lines.append(row['stage'])
    missing = list(dict.fromkeys(criterion.get('label') for qualification in (task['state'].get('qualifications') or {}).values()
        for criterion in (qualification.get('criteria') or {}).values()
        if criterion.get('status') != 'verified' and criterion.get('label')))
    if missing and not drafts: lines.append('Не подтверждено: ' + '; '.join(missing))
    action = task['presentation'].get('next_action') or {}
    if action.get('label'): lines.append('Следующий шаг: ' + action['label'])
    for index, draft in enumerate(drafts, 1):
        lines.extend([f"Письмо {index}. Статус: {draft['status']}",
            'Кому: ' + str(draft.get('recipient') or 'Не выбран'),
            'От: ' + str(draft.get('sender') or 'Не выбран'),
            'Тема: ' + str(draft.get('subject') or 'Не указана'),
            str(draft.get('generated_text') or 'Текст не подготовлен')])
        brief = draft.get('message_brief_json') or {}
        if brief.get('source_url'): lines.append('Источник персонализации: ' + str(brief['source_url']))
    if drafts: lines.append('Черновики не отправляются без отдельного просмотра и подтверждения отправки.')
    section = 'drafts' if drafts else 'companies'
    return {'status': 'clarification_required' if missing and not drafts else 'completed', 'chat_response': '\n\n'.join(lines), 'task': task,
        'search_task_id': task['id'], 'job_id': task['id'], 'drafts': drafts,
        'result_ref': {'href':f"/dashboard/partnerships?business_id={task['business_id']}&search_task_id={task['id']}&section={section}",
                       'label':'Посмотреть письма' if drafts else 'Посмотреть компании'},
        'external_dispatch_performed':False}


def record(cursor, row, state, status, stage):
    signature = json.dumps([status, state.get('blocker'), state.get('qualifications'), state.get('campaign_results')], sort_keys=True, default=str)
    event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'outreach-result:' + str(row['id']) + ':' + hashlib.sha256(signature.encode()).hexdigest()))
    cursor.execute('''INSERT INTO agent_action_ledger
        (id,business_id,action_type,capability,risk_level,input_summary,status,metadata_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING''',
        (event_id,row['business_id'],EVENT,'partnerships.continue_outreach','low',stage,'pending',
         Json({'job_id':str(row['id']),'operator_user_id':str(row['user_id']),'task_status':status,'next_chunk':0})))


async def deliver(application, host, transaction):
    def pending(cursor):
        cursor.execute('''SELECT e.id AS event_id,e.metadata_json,j.*,u.telegram_id
            FROM agent_action_ledger e JOIN operator_async_jobs j ON j.id::text=e.metadata_json->>'job_id'
            JOIN users u ON u.id=j.user_id
            WHERE e.action_type=%s AND e.status=%s AND EXISTS (
                SELECT 1 FROM operatormessages m WHERE m.business_id=j.business_id AND m.user_id=j.user_id
                AND (m.result_json->>'job_id'=j.id::text OR m.result_json#>>'{task,id}'=j.id::text))
            ORDER BY e.created_at LIMIT 10''',(EVENT,'pending'))
        return [dict(row) for row in cursor.fetchall()]
    for item in await asyncio.to_thread(transaction,pending):
        try:
            await deliver_item(application, host, transaction, item)
        except PermissionError:
            await asyncio.to_thread(transaction,lambda cursor:cursor.execute('UPDATE agent_action_ledger SET status=%s WHERE id=%s',('access_revoked',item['event_id'])))
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Outreach result notification failed; retrying journal entry without rerunning task')


async def deliver_item(application, host, transaction, item):
    if item['metadata_json'].get('task_status') != item['status']:
        await asyncio.to_thread(transaction,lambda cursor:cursor.execute('UPDATE agent_action_ledger SET status=%s WHERE id=%s',('superseded',item['event_id'])))
        return
    # Exact originating command, never whichever task or chat happened last.
    def prepare(cursor):
        from services.operator_audio import authorize_actor
        from services.operator_conversations import append_operator_message
        authorize_actor(cursor,item['user_id'],item['business_id'])
        cursor.execute('''SELECT m.conversation_id,c.channel FROM operatormessages m
            JOIN operatorconversations c ON c.id=m.conversation_id
            WHERE m.business_id=%s AND m.user_id=%s AND m.role IN (%s,%s)
              AND (m.result_json->>'job_id'=%s OR m.result_json#>>'{task,id}'=%s)
            ORDER BY m.created_at LIMIT 1''', (item['business_id'],item['user_id'],'operator','assistant',str(item['id']),str(item['id'])))
        origin=cursor.fetchone()
        if not origin: return None
        response=result(cursor,item)
        return dict(origin),response
    prepared=await asyncio.to_thread(transaction,prepare)
    if not prepared: return
    origin,response=prepared
    response['outreach_result_event_id'] = item['event_id']
    # Event id is distinct from job id (SELECT aliases below preserve both).
    event_id=item['event_id']
    def save_message(cursor):
        from services.operator_conversations import append_operator_message
        cursor.execute('SELECT metadata_json FROM agent_action_ledger WHERE id=%s FOR UPDATE',(event_id,))
        meta=dict(cursor.fetchone()['metadata_json'])
        if not meta.get('message_id'):
            meta['message_id']=append_operator_message(cursor,conversation_id=origin['conversation_id'],
                business_id=item['business_id'],user_id=item['user_id'],role='operator',
                content=response['chat_response'],capability='partnerships.continue_outreach',status=response['status'],result=response)
            cursor.execute('UPDATE agent_action_ledger SET metadata_json=%s WHERE id=%s',(Json(meta),event_id))
        return meta
    if origin['channel']=='telegram':
        current=await asyncio.to_thread(host._control_scope_business_context,str(item['telegram_id']))
        if not current or str(current['business_id'])!=str(item['business_id']) or str(current['user_id'])!=str(item['user_id']):
            return
    meta=await asyncio.to_thread(transaction,save_message)
    if origin['channel']=='telegram':
        chunks=split_telegram_text(response['chat_response'])
        for index in range(int(meta.get('next_chunk',0)),len(chunks)):
            await application.bot.send_message(chat_id=item['telegram_id'],text=chunks[index],
                reply_markup=host._build_operator_result_markup(response) if index==len(chunks)-1 else None)
            await asyncio.to_thread(transaction,lambda cursor:cursor.execute(
                'UPDATE agent_action_ledger SET metadata_json=metadata_json || %s WHERE id=%s',
                (Json({'next_chunk':index+1}),event_id)))
    await asyncio.to_thread(transaction,lambda cursor:cursor.execute('UPDATE agent_action_ledger SET status=%s WHERE id=%s',('delivered',event_id)))
