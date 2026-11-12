"""Shared platform/business outreach views through the existing durable job lane."""
import hashlib
import json
import os
import re
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


def require_outreach_scope(cursor, *, user_id, scope_kind='platform', scope_id=None, actor=None, write=False):
    """Use current DB rights, never an admin flag cached in a messenger JWT."""
    session = actor or {}
    if session.get('session_kind') == 'demo' or session.get('impersonating') or session.get('impersonated_by'):
        raise PermissionError('Рабочие данные недоступны в этой сессии')
    from services.business_permissions import load_actor
    from core.auth_helpers import verify_business_access, verify_business_write_access
    if scope_kind == 'platform':
        business = require_platform_actor(cursor, user_id, session)
        current = load_actor(cursor, user_id)
        return {'kind': 'platform', 'id': None, 'business_id': str(business['id']),
                'business_ids': [], 'name': business.get('name') or 'LocalOS', 'can_write': True, 'actor': current}
    if scope_kind != 'business' or not scope_id:
        raise PermissionError('Выберите доступный бизнес')
    current = load_actor(cursor, user_id)
    business_id = str(scope_id)
    if business_id == platform_business_id():
        raise PermissionError('Для LocalOS используйте платформенный контекст')
    if not verify_business_access(cursor, business_id, current)[0]:
        raise PermissionError('Нет доступа к бизнесу')
    can_write = verify_business_write_access(cursor, business_id, current)[0]
    if write and not can_write:
        raise PermissionError('Изменения недоступны в этом бизнесе')
    return {'kind': 'business', 'id': business_id, 'business_id': business_id,
            'business_ids': [business_id], 'name': '', 'can_write': can_write, 'actor': current}


def require_outreach_capability(scope):
    if scope['kind'] == 'platform':
        return
    from services.partnership_leads_service import get_capability_access
    if not get_capability_access(scope['business_id'], 'partnerships',
            bool(scope.get('actor', {}).get('is_superadmin'))).get('allowed'):
        raise PermissionError('Аутрич недоступен на текущем тарифе')


def _ownership(alias='inbound'):
    # Both canonical owners must agree when both are present. A lead's legacy
    # business/intent is deliberately not an authority for an inbound event.
    return "(campaign.business_id IS NULL OR workstream.client_business_id IS NULL OR campaign.business_id=workstream.client_business_id)"


def inbox_page(cursor, *, limit=20, before=None, business_id=None):
    limit = max(1, min(int(limit), 50))
    params = []
    conditions = [_ownership()]
    if business_id:
        conditions.append('COALESCE(workstream.client_business_id,campaign.business_id)=%s')
        params.append(business_id)
    if before and not business_id:
        before = str(uuid.UUID(str(before)))
        conditions.append('''(inbound.created_at,inbound.id) <
            (SELECT created_at,id FROM outreach_inbound_events WHERE id=%s)''')
        params.append(before)
    elif before:
        before = str(uuid.UUID(str(before)))
        # A foreign cursor cannot reveal its timestamp or advance this inbox.
        cursor.execute(f'''SELECT inbound.created_at,inbound.id FROM outreach_inbound_events inbound
            LEFT JOIN outreach_campaigns campaign ON campaign.id=inbound.campaign_id
            LEFT JOIN lead_workstreams workstream ON workstream.id=inbound.workstream_id
            WHERE inbound.id=%s AND inbound.is_human=TRUE AND {' AND '.join(conditions)}''',
            (before, *params))
        anchor = _row(cursor, cursor.fetchone())
        if not anchor:
            return {'items': [], 'cursor': None}
        conditions.append('(inbound.created_at,inbound.id)<(%s,%s)')
        params.extend([anchor['created_at'], before])
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
        WHERE inbound.is_human=TRUE AND {' AND '.join(conditions)}
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


def workspace(cursor, *, limit=20, before=None, scope=None, user_id=None):
    scope = scope or {'kind': 'platform', 'business_id': platform_business_id(), 'can_write': True}
    business_id = scope['business_id'] if scope['kind'] == 'business' else None
    page = inbox_page(cursor, limit=limit, before=before, business_id=business_id)
    sender_filter = '' if not business_id else '''AND ((sender.scope_type='business' AND sender.business_id=%s)
        OR (sender.scope_type='platform' AND EXISTS (SELECT 1 FROM outreach_campaign_touches touch
            JOIN outreach_campaigns campaign ON campaign.id=touch.campaign_id
            JOIN lead_workstreams workstream ON workstream.id=campaign.workstream_id
            WHERE touch.sender_account_id=sender.id AND campaign.business_id=%s
              AND (workstream.client_business_id IS NULL OR workstream.client_business_id=campaign.business_id))))'''
    cursor.execute(f'''SELECT sender.id,sender.channel,sender.status,sender.sender_identity,sender.display_name,
            sender.business_id,business.name AS business_name,sender.last_reply_sync_at,
            (NULLIF(sender.reply_sync_error,'') IS NOT NULL) AS sync_failed
        FROM outreach_sender_accounts sender LEFT JOIN businesses business ON business.id=sender.business_id
        WHERE sender.status IN ('connected','attention') {sender_filter}
        ORDER BY sender.channel,sender.id LIMIT 200''', (business_id,business_id) if business_id else ())
    senders = [_row(cursor, row) for row in cursor.fetchall()]
    params = (business_id,user_id) if business_id else (user_id,)
    search_filter = 'AND job.business_id=%s AND job.user_id=%s' if business_id else 'AND job.user_id=%s'
    cursor.execute(f'''SELECT job.id,job.business_id,business.name AS business_name,
            job.status,job.stage,job.payload_json->>'audience' AS audience,
            job.payload_json->>'target_count' AS target_count,job.updated_at
        FROM operator_async_jobs job LEFT JOIN businesses business ON business.id=job.business_id
        WHERE job.kind='outreach_continue' {search_filter}
        ORDER BY job.created_at DESC LIMIT 50''',params)
    searches = [_row(cursor, row) for row in cursor.fetchall()]
    cursor.execute('''SELECT * FROM operator_async_jobs WHERE kind=%s AND business_id=%s AND user_id=%s
        AND status IN ('queued','running') ORDER BY created_at LIMIT 1''',
        (SYNC_KIND, scope['business_id'], user_id))
    from services.operator_async_jobs import _public_job
    active = _row(cursor, cursor.fetchone())
    cursor.execute('''SELECT * FROM operator_async_jobs WHERE kind=%s AND business_id=%s AND user_id=%s
        ORDER BY created_at DESC,id DESC LIMIT 1''',(SYNC_KIND,scope['business_id'],user_id))
    last_check = _row(cursor,cursor.fetchone())
    last_public = _public_job(last_check) if last_check else None
    if last_public and last_public.get('error'):
        last_public['error'] = 'Проверка не завершена. Повторите запрос.'
    from services.outreach_continuation import continuation_enabled
    from services.outreach_web_search import configured
    return {**page, 'senders': senders, 'searches': searches,
            'scope': {'kind': scope['kind'], 'id': business_id}, 'can_write': scope.get('can_write',False),
            'as_of': datetime.now(timezone.utc).isoformat(),
            'active_job': _public_job(active) if active else None, 'last_check': last_public,
            'readiness': {'search_enabled': continuation_enabled(scope['business_id']),
                          'web_enabled': configured(), 'yandex_enabled': configured('yandex'),
                          'sync_enabled': sync_enabled()}}


def sync_enabled():
    return os.getenv('OUTREACH_REPLY_SYNC_ENABLED', 'true').lower() in {'true', '1', 'yes'}


def _business_sources(cursor, business_id):
    # Every source is restricted to a canonical campaign. This also protects a
    # business-owned sender accidentally used in another tenant's queue.
    cursor.execute('''SELECT DISTINCT sender.id AS sender_account_id,sender.channel,
            campaign.id AS campaign_id
        FROM outreach_sender_accounts sender
        JOIN outreach_campaign_touches touch ON touch.sender_account_id=sender.id
        JOIN outreach_campaigns campaign ON campaign.id=touch.campaign_id
        JOIN lead_workstreams workstream ON workstream.id=campaign.workstream_id
        WHERE campaign.business_id=%s
          AND (workstream.client_business_id IS NULL OR workstream.client_business_id=campaign.business_id)
          AND (sender.scope_type='platform' OR (sender.scope_type='business' AND sender.business_id=%s))
          AND sender.status IN ('connected','attention')
          AND sender.channel IN ('email','telegram','vk')
          AND sender.outreach_enabled=TRUE
        ORDER BY sender.id,campaign.id LIMIT 201''', (business_id,business_id))
    rows = [_row(cursor, row) for row in cursor.fetchall()]
    return [{key: str(row[key]) for key in ('sender_account_id','channel','campaign_id')} for row in rows[:200]], len(rows)>200


def enqueue_reply_sync(cursor, *, user_id, request_id=None, scope=None, actor=None):
    if scope is None:
        require_platform_actor(cursor,user_id,actor)
        scope={'kind':'platform','business_id':platform_business_id()}
    else:
        scope = require_outreach_scope(cursor,user_id=user_id,scope_kind=scope['kind'],
            scope_id=scope.get('id'),actor=actor,write=True)
    require_outreach_capability(scope)
    if not sync_enabled():
        raise ValueError('Обновление входящих временно отключено')
    from services.operator_async_jobs import create_operator_async_job, _public_job
    sources,truncated = _business_sources(cursor,scope['business_id']) if scope['kind']=='business' else ([],False)
    payload={'scope_kind':scope['kind'],'scope_id':scope.get('id'),'sources':sources,'sources_truncated':truncated}
    lock_key=f"{SYNC_KIND}:{user_id}:{scope['kind']}:{scope['business_id']}"
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(lock_key,))
    cursor.execute('''SELECT * FROM operator_async_jobs WHERE kind=%s AND business_id=%s AND user_id=%s
        AND status IN ('queued','running') ORDER BY created_at LIMIT 1''',
        (SYNC_KIND,scope['business_id'],user_id))
    existing=_row(cursor,cursor.fetchone())
    if existing:
        return _public_job(existing)
    request_id=str(request_id or uuid.uuid4())
    if len(request_id)>200:
        raise ValueError('Некорректный идентификатор запроса')
    key=hashlib.sha256(f"{scope['kind']}:{scope['business_id']}:{request_id}".encode()).hexdigest()
    return create_operator_async_job(cursor,user_id=user_id,business_id=scope['business_id'],
        action_id=None,kind=SYNC_KIND,payload=payload,idempotency_key=f'{SYNC_KIND}:{key}',
        stage='Проверяем ответы в подключённых каналах',max_attempts=1)


def _payload(job):
    value=job.get('payload_json') or {}
    return json.loads(value) if isinstance(value,str) else value


def _authorize_job(job):
    if not sync_enabled():
        raise ValueError('Обновление входящих временно отключено')
    from pg_db_utils import get_db_connection
    connection=get_db_connection()
    try:
        payload=_payload(job)
        kind=payload.get('scope_kind') or 'platform'
        scope_id=payload.get('scope_id')
        expected=platform_business_id() if kind=='platform' else scope_id
        if job.get('business_id')!=expected:
            raise PermissionError('Неверный контекст проверки входящих')
        scope=require_outreach_scope(connection.cursor(),user_id=str(job.get('user_id') or ''),
            scope_kind=kind,scope_id=scope_id,write=True)
        require_outreach_capability(scope)
        if kind=='business':
            current,_=_business_sources(connection.cursor(),scope['business_id'])
            allowed={json.dumps(item,sort_keys=True) for item in current}
            if any(json.dumps(item,sort_keys=True) not in allowed for item in payload.get('sources',[])):
                raise PermissionError('Источник проверки больше недоступен')
        return scope
    finally:
        connection.close()


def sync_reply_channels(sources=None):
    from api.admin_prospecting import _sync_telegram_app_replies
    from services.outreach_email_reply_service import sync_email_replies
    from services.outreach_vk_reply_service import sync_vk_replies
    if sources is None:
        return (('telegram',lambda:_sync_telegram_app_replies(limit=200)),
                ('vk',lambda:sync_vk_replies(sender_limit=200,per_conversation_limit=50)),
                ('email',lambda:sync_email_replies(sender_limit=200,per_sender_limit=100)))
    collectors=[]
    from services.outreach_reply_scope_guard import assert_campaign_peer_isolation
    for source in sources:
        sender=source['sender_account_id']; campaign=source['campaign_id']; channel=source['channel']
        def collect(sender=sender,campaign=campaign,channel=channel):
            assert_campaign_peer_isolation(sender,campaign,channel)
            if channel=='email':
                return sync_email_replies(sender_account_id=sender,campaign_id=campaign,sender_limit=1,per_sender_limit=100)
            if channel=='vk':
                return sync_vk_replies(sender_account_id=sender,campaign_id=campaign,sender_limit=1,per_conversation_limit=50)
            return _sync_telegram_app_replies(sender_account_id=sender,campaign_id=campaign,limit=200)
        collectors.append((channel,collect))
    return collectors


def process_reply_sync(job):
    if not sync_enabled():
        raise ValueError('Обновление входящих временно отключено')
    _authorize_job(job)
    payload=_payload(job)
    client=payload.get('scope_kind')=='business'
    sources=payload.get('sources',[]) if client else None
    summaries=[]
    collectors=sync_reply_channels(sources) if client else sync_reply_channels()
    for index,(channel,collect) in enumerate(collectors):
        _authorize_job(job)
        source=sources[index] if client else {}
        try:
            result=collect()
            summary={'channel':channel,'picked':int(result.get('picked') or 0),
                     'imported':int(result.get('imported') or 0),
                     'failed':int(result.get('failed') or 0) or int(result.get('success') is False)}
        except Exception:
            summary={'channel':channel,'picked':0,'imported':0,'failed':1}
        summary.update(source)
        summary['business_id']=job['business_id'] if client else None
        summary['status']='failed' if summary['failed'] else 'checked' if summary['picked'] else 'no_sources'
        summary['error_code']='source_sync_failed' if summary['failed'] else None
        summary['checked_at']=None if summary['failed'] else datetime.now(timezone.utc).isoformat()
        summaries.append(summary)
    _authorize_job(job)
    failed=any(item['failed'] for item in summaries) or payload.get('sources_truncated',False)
    picked=sum(item['picked'] for item in summaries)
    status='partial' if failed else 'checked' if picked else 'no_sources'
    prefix=('Часть каналов не удалось обновить. Показаны доступные сохранённые ответы.' if failed else
            'Проверка подключённых каналов завершена в пределах одного прохода.' if picked else
            'В этом проходе не было источников или диалогов, доступных для проверки. Показаны сохранённые ответы.')
    from pg_db_utils import get_db_connection
    connection=get_db_connection()
    try:
        cursor=connection.cursor()
        if client:
            page=inbox_page(cursor,business_id=job['business_id'])
            lines=[str(item.get('reply_text') or '')[:240] for item in page['items'][:5]]
            result={'status':'completed','capability':'partnerships.read','chat_response':'\n'.join(lines) or 'Сохранённых ответов пока нет.',
                    'mobile_route':{'screen':'partnerships'},'external_writes_performed':False,**page}
        else:
            from services.operator_platform_context import _incoming
            result=_incoming(cursor,{'kind':'platform','name':'LocalOS'},sync_checked=True)
        result.update(sync_status=status,channels=summaries,checked_at=datetime.now(timezone.utc).isoformat(),
                      scope={'kind':'business' if client else 'platform','id':job['business_id'] if client else None},
                      mail_read_scope='outreach_replies',
                      result_target={'screen':'partnerships','business_id':job['business_id'], 'label':'Открыть входящие'})
        result['chat_response']=prefix+'\n\n'+result['chat_response']
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


def business_read_request(cursor, *, business_id, user_id, message, actor=None, request_id=None):
    """Deterministic business inbox read/refresh shared by chat surfaces."""
    if business_id == platform_business_id():
        return None
    incoming = re.search(r'входящ|ответ[ыаов]*.{0,30}(?:аутрич|рассыл|партн|кампан)|inbox|incoming', message, re.I)
    if not incoming or re.search(r'отправ|опублику|удал|запуст|ответь|разошл|измени|подготов|созда',message,re.I):
        return None
    scope=require_outreach_scope(cursor,user_id=user_id,scope_kind='business',scope_id=business_id,actor=actor)
    require_outreach_capability(scope)
    if re.search(r'проверь|проверить|обнови|обновить|синхрониз|check|refresh',message,re.I):
        job=enqueue_reply_sync(cursor,user_id=user_id,request_id=request_id,scope=scope,actor=actor)
        return {'status':'processing','capability':'partnerships.read','async_job_id':job['id'],'job':job,
                'chat_response':'Проверка ответов аутрича поставлена в очередь. Результат появится здесь и в разделе «Партнёрства».',
                'mobile_route':{'screen':'partnerships'},'external_writes_performed':False}
    page=inbox_page(cursor,business_id=business_id)
    lines=['Сохранённые ответы аутрича (без новой проверки каналов):']
    for reply in page['items'][:5]:
        lines.append(f"• {reply.get('lead_name') or 'Компания'} · {reply.get('channel') or ''}")
        lines.append(str(reply.get('reply_text') or 'Текст ответа не сохранён')[:500])
    if not page['items']:
        lines.append('Сохранённых ответов пока нет. Для обновления: «Проверь входящие».')
    return {'status':'completed','capability':'partnerships.read','chat_response':'\n'.join(lines),**page,
            'scope':{'kind':'business','id':business_id},'mobile_route':{'screen':'partnerships'},
            'external_writes_performed':False,'sync_checked':False}
