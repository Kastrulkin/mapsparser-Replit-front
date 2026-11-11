"""Platform outreach views and bounded reads through existing reply adapters."""
import json
import os
import uuid
from datetime import datetime, timezone

from services.operator_conversations import _row
from services.operator_platform_context import platform_business_id, platform_chat_business


SYNC_KIND = 'outreach_inbox_sync'


def require_platform_actor(cursor, user_id, actor=None):
    actor = actor or {}
    if actor.get('session_kind') == 'demo' or actor.get('impersonating') or actor.get('impersonated_by'):
        raise PermissionError('Нужен собственный доступ к платформе LocalOS')
    business = platform_chat_business(cursor, user_id)
    if not business:
        raise PermissionError('Нет доступа к платформе LocalOS')
    return business


def inbox_page(cursor, *, limit=20, before=None):
    limit = max(1, min(int(limit), 50))
    params = []
    condition = ''
    if before:
        before = str(uuid.UUID(str(before)))
        condition = '''AND (inbound.created_at,inbound.id) <
            (SELECT created_at,id FROM outreach_inbound_events WHERE id=%s)'''
        params.append(before)
    params.append(limit + 1)
    cursor.execute(f'''SELECT inbound.id, inbound.channel, inbound.classification,
            inbound.occurred_at, inbound.created_at,
            COALESCE(inbound.raw_payload_json->>'raw_reply','') AS reply_text,
            lead.name AS lead_name,
            COALESCE(workstream.client_business_id,campaign.business_id) AS business_id,
            business.name AS business_name
        FROM outreach_inbound_events inbound
        LEFT JOIN outreach_campaigns campaign ON campaign.id=inbound.campaign_id
        LEFT JOIN lead_workstreams workstream ON workstream.id=inbound.workstream_id
        LEFT JOIN prospectingleads lead ON lead.id=inbound.lead_id
        LEFT JOIN businesses business ON business.id=COALESCE(workstream.client_business_id,campaign.business_id)
        WHERE inbound.is_human=TRUE {condition}
        ORDER BY inbound.created_at DESC,inbound.id DESC LIMIT %s''', tuple(params))
    rows = [_row(cursor, row) for row in cursor.fetchall()]
    items = []
    for row in rows[:limit]:
        row['id'] = str(row['id'])
        row['reply_text'] = str(row.get('reply_text') or '')[:20000]
        for key in ('created_at', 'occurred_at'):
            if hasattr(row.get(key), 'isoformat'):
                row[key] = row[key].isoformat()
        items.append(row)
    return {'items': items, 'cursor': items[-1]['id'] if len(rows) > limit else None}


def workspace(cursor, *, limit=20, before=None):
    page = inbox_page(cursor, limit=limit, before=before)
    cursor.execute('''SELECT channel, status, last_reply_sync_at,
            (reply_sync_error IS NOT NULL) AS sync_failed
        FROM outreach_sender_accounts WHERE status IN ('connected','attention')
        ORDER BY channel,id''')
    senders = [_row(cursor, row) for row in cursor.fetchall()]
    cursor.execute('''SELECT job.id,job.business_id,business.name AS business_name,
            job.status,job.stage,job.payload_json->>'audience' AS audience,
            job.payload_json->>'target_count' AS target_count,job.updated_at
        FROM operator_async_jobs job LEFT JOIN businesses business ON business.id=job.business_id
        WHERE job.kind='outreach_continue' ORDER BY job.created_at DESC LIMIT 50''')
    searches = [_row(cursor, row) for row in cursor.fetchall()]
    cursor.execute('''SELECT * FROM operator_async_jobs WHERE kind=%s AND business_id=%s
        AND status IN ('queued','running') ORDER BY created_at LIMIT 1''',
        (SYNC_KIND, platform_business_id()))
    from services.operator_async_jobs import _public_job
    active = _row(cursor, cursor.fetchone())
    from services.outreach_continuation import continuation_enabled
    from services.outreach_web_search import configured
    return {**page, 'senders': senders, 'searches': searches,
            'active_job': _public_job(active) if active else None,
            'readiness': {'search_enabled': continuation_enabled(platform_business_id()),
                          'web_enabled': configured(), 'yandex_enabled': configured('yandex'),
                          'sync_enabled': sync_enabled()}}


def sync_enabled():
    return os.getenv('OUTREACH_REPLY_SYNC_ENABLED', 'true').lower() in {'true', '1', 'yes'}


def enqueue_reply_sync(cursor, *, user_id, request_id=None):
    require_platform_actor(cursor, user_id)
    if not sync_enabled():
        raise ValueError('Обновление входящих временно отключено')
    from services.operator_async_jobs import create_operator_async_job, _public_job
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (SYNC_KIND,))
    cursor.execute('''SELECT * FROM operator_async_jobs WHERE kind=%s AND business_id=%s AND user_id=%s
        AND status IN ('queued','running') ORDER BY created_at LIMIT 1''',
        (SYNC_KIND, platform_business_id(), user_id))
    existing = _row(cursor, cursor.fetchone())
    if existing:
        return _public_job(existing)
    request_id = str(request_id or uuid.uuid4())
    if len(request_id) > 200:
        raise ValueError('Некорректный идентификатор запроса')
    return create_operator_async_job(cursor, user_id=user_id, business_id=platform_business_id(),
        action_id=None, kind=SYNC_KIND, payload={}, idempotency_key=f'{SYNC_KIND}:{request_id}',
        stage='Проверяем ответы в подключённых каналах', max_attempts=1)


def _authorize_job(job):
    if not sync_enabled():
        raise ValueError('Обновление входящих временно отключено')
    from pg_db_utils import get_db_connection
    connection = get_db_connection()
    try:
        if job.get('business_id') != platform_business_id():
            raise PermissionError('Неверный контекст проверки входящих')
        require_platform_actor(connection.cursor(), str(job.get('user_id') or ''))
    finally:
        connection.close()


def sync_reply_channels():
    # These existing adapters only collect replies; none dispatch outreach.
    from api.admin_prospecting import _sync_telegram_app_replies
    from services.outreach_email_reply_service import sync_email_replies
    from services.outreach_vk_reply_service import sync_vk_replies
    return (
        ('telegram', lambda: _sync_telegram_app_replies(limit=200)),
        ('vk', lambda: sync_vk_replies(sender_limit=200, per_conversation_limit=50)),
        ('email', lambda: sync_email_replies(sender_limit=200, per_sender_limit=100)),
    )


def process_reply_sync(job):
    if not sync_enabled():
        raise ValueError('Обновление входящих временно отключено')
    _authorize_job(job)
    summaries = []
    for channel, collect in sync_reply_channels():
        _authorize_job(job)
        try:
            result = collect()
            summaries.append({'channel': channel, 'picked': int(result.get('picked') or 0),
                              'imported': int(result.get('imported') or 0),
                              'failed': int(result.get('failed') or 0) or int(result.get('success') is False)})
        except Exception:
            summaries.append({'channel': channel, 'picked': 0, 'imported': 0, 'failed': 1})
    _authorize_job(job)
    from pg_db_utils import get_db_connection
    from services.operator_platform_context import _incoming
    failed = any(item['failed'] for item in summaries)
    picked = sum(item['picked'] for item in summaries)
    status = 'partial' if failed else 'checked' if picked else 'no_sources'
    prefix = ('Часть каналов не удалось обновить. Показаны доступные сохранённые ответы.' if failed else
              'Проверка подключённых каналов завершена в пределах одного прохода.' if picked else
              'В этом проходе не было источников или диалогов, доступных для проверки. Показаны сохранённые ответы.')
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        result = _incoming(cursor, {'kind': 'platform', 'name': 'LocalOS'}, sync_checked=True)
        result.update(sync_status=status, channels=summaries, checked_at=datetime.now(timezone.utc).isoformat())
        result['chat_response'] = prefix + '\n\n' + result['chat_response']
        if job.get('id') and job.get('lease_token'):
            cursor.execute('''UPDATE operatormessages SET content=%s,status=%s,
                    result_json=COALESCE(result_json,'{}'::jsonb)||%s::jsonb
                WHERE business_id=%s AND user_id=%s AND role='operator'
                  AND result_json->>'async_job_id'=%s
                  AND EXISTS (SELECT 1 FROM operator_async_jobs WHERE id=%s
                    AND lease_token=%s AND status='running')''',
                (result['chat_response'],result['status'],json.dumps(result,default=str),
                 job['business_id'],job['user_id'],str(job['id']),job['id'],job['lease_token']))
            connection.commit()
        return result
    finally:
        connection.close()
