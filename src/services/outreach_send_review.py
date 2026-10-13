"""Exact-current-version send review over native campaigns and send queue.

No generation, provider call, new scheduler or independent delivery store.
The existing Operator approval record supplies replay protection and transaction.
"""
import hashlib
import json
import uuid


def prior_first_contact(cursor, business_id, lead_id):
    cursor.execute('''SELECT EXISTS (
        SELECT 1 FROM outreachsendqueue q
        JOIN outreach_campaign_touches t ON t.id=q.campaign_touch_id
        JOIN outreach_campaigns c ON c.id=t.campaign_id
        WHERE c.business_id=%s AND c.lead_id=%s AND t.channel='email'
          AND (NULLIF(q.provider_message_id,'') IS NOT NULL
               OR q.delivery_status IN ('queued','sending','retry','retry_wait','sent','delivered','read','replied','delivery_unknown','unknown','uncertain')
               OR lower(COALESCE(q.error_text,'')) LIKE '%%send_uncertain%%')) AS contacted''',
        (business_id,lead_id))
    return bool((cursor.fetchone() or {}).get('contacted'))


def review_digest(review):
    return hashlib.sha256(json.dumps(review, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), default=str).encode()).hexdigest()


def load_review(cursor, *, business_id, user_id, task_ids, lock=False):
    from services.operator_audio import authorize_actor
    from services.outreach_safety_service import approval_snapshot_hash
    actor, _ = authorize_actor(cursor, user_id, business_id)
    from services.outreach_continuation import actor_can_write
    if not actor_can_write(cursor, business_id, {**actor, 'user_id': user_id}):
        raise PermissionError('send_review_access_denied')
    ids = sorted(set(str(value) for value in task_ids))
    if not ids or len(ids) > 10:
        raise ValueError('send_groups_required')
    campaigns = []
    revisions = []
    for task_id in ids:
        cursor.execute("SELECT * FROM operator_async_jobs WHERE id::text=%s AND business_id=%s AND kind='outreach_continue'" +
                       (' FOR UPDATE' if lock else ''), (task_id, business_id))
        task = cursor.fetchone()
        if not task:
            raise ValueError('search_task_not_found')
        if task.get('status') in {'queued', 'running'}:
            raise ValueError('pause_before_send_review')
        state = task.get('result_json') or {}
        revisions.append([task_id, task.get('payload_json')])
        contacts = set(state.get('verified_contact_workstream_ids') or [])
        for ws_id, value in (state.get('campaign_results') or {}).items():
            if not value.get('campaign_id'):
                continue
            if (value.get('status') != 'ready' or ws_id not in contacts or
                    (state.get('qualifications', {}).get(ws_id) or {}).get('status') != 'qualified'):
                raise ValueError('letters_need_review')
            campaigns.append(str(value['campaign_id']))
    campaigns = sorted(set(campaigns))
    if not campaigns:
        raise ValueError('no_send_ready_letters')
    letters = []
    leads, recipients = set(), set()
    for campaign_id in campaigns:
        cursor.execute('SELECT * FROM outreach_campaigns WHERE id=%s AND business_id=%s' +
                       (' FOR UPDATE' if lock else ''), (campaign_id, business_id))
        campaign = cursor.fetchone()
        if not campaign or campaign['status'] != 'draft':
            raise ValueError('send_review_stale')
        cursor.execute('''SELECT t.*, cp.normalized_value AS recipient,
            s.sender_identity AS sender FROM outreach_campaign_touches t
            JOIN lead_contact_points cp ON cp.id=t.contact_point_id AND cp.lead_id=%s
            JOIN outreach_sender_accounts s ON s.id=t.sender_account_id
            WHERE t.campaign_id=%s ORDER BY t.sequence_index''' +
                       (' FOR UPDATE OF t,cp,s' if lock else ''), (campaign['lead_id'], campaign_id))
        touches = [dict(row) for row in cursor.fetchall()]
        # A review of first emails never silently approves further touches.
        if len(touches) != 1 or touches[0].get('sequence_index') != 0:
            raise ValueError('first_email_only_required')
        touch = touches[0]
        if (touch.get('channel') != 'email' or not touch.get('recipient') or not touch.get('sender')
                or not touch.get('generated_text') or not touch.get('subject')
                or (touch.get('quality_gate_json') or {}).get('passed') is not True):
            raise ValueError('letter_not_send_ready')
        lead_id = str(campaign['lead_id'])
        recipient = str(touch['recipient']).casefold()
        if lock:
            cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                           ('reviewed-first-email:' + business_id + ':' + lead_id,))
        if lead_id in leads or recipient in recipients:
            raise ValueError('duplicate_first_contact')
        from services.outreach_safety_service import load_partnership_repeat_contact_guard
        if load_partnership_repeat_contact_guard(cursor, lead_id=lead_id,
                workstream_id=str(campaign.get('workstream_id') or '') or None).get('blocked'):
            raise ValueError('reply_or_refusal_received')
        if prior_first_contact(cursor,business_id,lead_id):
            raise ValueError('first_contact_exists')
        leads.add(lead_id); recipients.add(recipient)
        letters.append({'id': str(touch['id']), 'campaign_id': campaign_id,
                        'lead_id': lead_id,
                        'recipient': touch['recipient'], 'sender': touch['sender'],
                        'subject': touch['subject'], 'generated_text': touch['generated_text'],
                        'status': 'draft', 'snapshot': approval_snapshot_hash(dict(campaign), touches),
                        'source_url': (touch.get('message_brief_json') or {}).get('source_url')})
    return {'business_id': business_id, 'user_id': user_id, 'task_ids': ids,
            'revisions': revisions, 'letters': letters}


def preview(cursor, *, business_id, user_id, task_ids):
    review = load_review(cursor, business_id=business_id, user_id=user_id, task_ids=task_ids)
    lines = ['Проверьте письма перед отправкой. В очередь попадут только показанные версии.']
    for index, letter in enumerate(review['letters'], 1):
        lines.append(f"Письмо {index}\nКому: {letter['recipient']}\nОт: {letter['sender']}\nТема: {letter['subject']}\n\n{letter['generated_text']}")
    lines.append('Подтверждение поставит эти письма в штатную очередь. Повторные касания не включены.')
    summary = '\n\n'.join(lines)
    return {'status': 'approval_required', 'chat_response': summary,
            'send_review': review['letters'], 'external_dispatch_performed': False,
            'approval': {'status': 'pending', 'capability': 'partnerships.send_review',
                         'summary': summary, 'envelope': {
                             'operation': 'confirm_send', 'business_id': business_id,
                             'task_ids': review['task_ids'], 'review_hash': review_digest(review)}}}


def confirm(cursor, *, business_id, user_id, envelope):
    from services.outreach_campaign_service import approve_campaign
    if envelope.get('business_id') != business_id:
        raise ValueError('send_review_business_mismatch')
    # All relevant campaign/touch/contact/sender rows locked before first mutation.
    review = load_review(cursor, business_id=business_id, user_id=user_id,
                         task_ids=envelope.get('task_ids') or [], lock=True)
    if review_digest(review) != envelope.get('review_hash'):
        raise ValueError('send_review_stale')
    cursor.execute('SAVEPOINT reviewed_group_send')
    try:
        batch_id = str(uuid.uuid4())
        cursor.execute('''INSERT INTO outreachsendbatches
            (id,batch_date,daily_limit,status,created_by,created_at,updated_at)
            VALUES (%s,(NOW() AT TIME ZONE 'Europe/Moscow')::date,%s,'draft',%s,NOW(),NOW())''',
            (batch_id, len(review['letters']), user_id))
        for letter in review['letters']:
            # Retains native grants, source freshness, sender readiness, suppression,
            # limits and idempotent queue keys. No direct provider send here.
            approve_campaign(cursor, letter['campaign_id'], user_id=user_id, reviewed_batch_id=batch_id)
        cursor.execute("UPDATE outreachsendbatches SET status='approved',approved_by=%s,updated_at=NOW() WHERE id=%s", (user_id,batch_id))
        cursor.execute('RELEASE SAVEPOINT reviewed_group_send')
    except Exception:
        cursor.execute('ROLLBACK TO SAVEPOINT reviewed_group_send')
        cursor.execute('RELEASE SAVEPOINT reviewed_group_send')
        raise
    return {'status': 'completed', 'chat_response': f"В очереди: {len(review['letters'])}. Подтверждения провайдера пока нет.",
            'batch_id': batch_id, 'task_ids': review['task_ids'],
            'external_dispatch_performed': False, 'delivery_status': 'queued'}
