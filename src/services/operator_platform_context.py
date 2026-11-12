"""The existing LocalOS system business anchors platform chat and its history.

Selection never grants privileges: every aggregate read checks the current actor.
No system business is created here. Explicit checks queue existing reply collectors.
"""
import os
import re
from datetime import datetime, timezone

from services.operator_conversations import _row


def platform_business_id():
    return os.getenv('LOCALOS_PLATFORM_BUSINESS_ID', '').strip() or 'localos-platform-telegram-radar'


def platform_chat_business(cursor, user_id):
    cursor.execute('''SELECT business.id, business.name, business.owner_id
        FROM businesses business JOIN users actor ON actor.id=%s
        WHERE business.id=%s AND COALESCE(business.is_active,TRUE)
          AND actor.is_superadmin=TRUE AND COALESCE(actor.is_active,TRUE)''',
        (user_id, platform_business_id()))
    return _row(cursor, cursor.fetchone())


def platform_read_request(cursor, *, business_id, user_id, message, actor=None, request_id=None):
    if business_id != platform_business_id():
        return None
    incoming = bool(re.search(r'входящ|ответ[ыаов]*.{0,30}(?:аутрич|рассыл|партн|кампан)|inbox|incoming', message, re.I))
    overview = bool(re.search(r'статус|сводк|обзор|контрол|что.{0,15}(?:важно|требует внимания)', message, re.I))
    if not incoming and not overview:
        return None
    # Mutations continue through the existing preview/approval router.
    if re.search(r'отправ|опублику|удал|запуст|ответь|разошл|измени|подготов|созда', message, re.I):
        return None
    from services.operator_platform_outreach import require_platform_actor
    require_platform_actor(cursor, user_id, actor)
    scope = {'kind': 'platform', 'id': None, 'name': 'LocalOS', 'business_ids': []}
    if incoming:
        if re.search(r'проверь|проверить|обнови|обновить|синхрониз|check|refresh', message, re.I):
            from services.operator_platform_outreach import enqueue_reply_sync
            job = enqueue_reply_sync(cursor, user_id=user_id, actor=actor, request_id=request_id)
            return {'status': 'processing', 'capability': 'partnerships.read',
                    'async_job_id': job['id'], 'job': job,
                    'chat_response': 'Проверка ответов в подключённых каналах поставлена в очередь. Итог и ответы доступны в разделе «Партнёрства» для всей платформы.',
                    'mobile_route': {'screen': 'partnerships'}, 'external_writes_performed': False}
        return _incoming(cursor, scope)
    from services.operator_scope_summary import build_operator_scope_summary, format_scope_summary_for_telegram
    summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
    return {'status': 'completed', 'capability': 'operator.query',
            'chat_response': format_scope_summary_for_telegram(summary), 'summary_data': summary,
            'mobile_route': {'screen': 'tasks'}, 'external_writes_performed': False}


def _incoming(cursor, scope, *, sync_checked=False):
    cursor.execute("SELECT to_regclass('public.outreach_inbound_events') AS table_ref")
    if not _row(cursor, cursor.fetchone()).get('table_ref'):
        return {'status': 'blocked', 'capability': 'partnerships.read',
                'chat_response': 'Входящие ответы аутрича пока недоступны в LocalOS.',
                'mobile_route': {'screen': 'partnerships'}, 'external_writes_performed': False}
    # Workstream-only replies have no campaign_id; keep them in the same inbox.
    cursor.execute('''SELECT inbound.id, inbound.channel, inbound.occurred_at,
            inbound.raw_payload_json->>'raw_reply' AS reply_text,
            lead.name AS lead_name, business.name AS business_name
        FROM outreach_inbound_events inbound
        LEFT JOIN outreach_campaigns campaign ON campaign.id=inbound.campaign_id
        LEFT JOIN lead_workstreams workstream ON workstream.id=inbound.workstream_id
        LEFT JOIN prospectingleads lead ON lead.id=inbound.lead_id
        LEFT JOIN businesses business ON business.id=COALESCE(workstream.client_business_id,campaign.business_id)
        WHERE inbound.is_human=TRUE
        ORDER BY inbound.occurred_at DESC, inbound.created_at DESC, inbound.id DESC LIMIT 21''')
    rows = [_row(cursor, row) for row in cursor.fetchall()]
    lines = ['LocalOS · Все бизнесы', '', 'Последние входящие ответы, сохранённые в LocalOS:']
    if not rows:
        lines.append('Сохранённых ответов пока нет.')
    for row in rows[:5]:
        observed = row.get('occurred_at')
        stamp = observed.isoformat() if hasattr(observed, 'isoformat') else str(observed or 'дата неизвестна')
        lines.append(f"• {str(row.get('lead_name') or 'Компания')[:60]} · {str(row.get('business_name') or 'LocalOS')[:60]} · {row.get('channel') or 'канал не указан'} · {stamp}")
        lines.append(str(row.get('reply_text') or 'Текст ответа не сохранён')[:240])
    if len(rows) > 5:
        lines.append('Показаны последние 5 ответов. Остальные — в разделе «Партнёрства».')
    cursor.execute("SELECT to_regclass('public.outreach_sender_accounts') AS table_ref")
    if _row(cursor, cursor.fetchone()).get('table_ref'):
        cursor.execute('''SELECT channel, last_reply_sync_at, reply_sync_error
            FROM outreach_sender_accounts WHERE status IN ('connected','attention')
            ORDER BY channel,id LIMIT 30''')
        sync = [_row(cursor, row) for row in cursor.fetchall()]
        if sync:
            lines.extend(['', 'Последняя синхронизация подключённых отправителей:'])
            for sender in sync[:6]:
                observed = sender.get('last_reply_sync_at')
                stamp = observed.isoformat() if hasattr(observed, 'isoformat') else str(observed or 'ещё не подтверждена')
                lines.append(f"• {sender.get('channel')}: {stamp}" + (' · есть ошибка синхронизации' if sender.get('reply_sync_error') else ''))
            if len(sync) > 6:
                lines.append('Состояние остальных отправителей — в настройках аутрича.')
    lines.extend(['', 'Один проход охватывает только подключённые источники. Личные диалоги MAX не читаются.' if sync_checked else 'Показаны полученные LocalOS ответы. Новая проверка почтовых ящиков и мессенджеров этим запросом не запускалась.'])
    return {'status': 'completed', 'capability': 'partnerships.read', 'chat_response': '\n'.join(lines),
            'scope': scope, 'as_of': datetime.now(timezone.utc).isoformat(),
            'mobile_route': {'screen': 'partnerships'}, 'external_writes_performed': False}
