"""One explicitly reviewed control email, using native campaigns and delivery queue.

No provider call here. Confirmation creates one touch; ordinary worker/reply sync
retain all sender, suppression, daily-limit and uncertainty checks.
"""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from psycopg2.extras import Json, RealDictCursor

CAPABILITY = 'communications.control_email'
BODY = 'Это контрольное письмо для проверки отправки и отслеживания ответа.'
SUBJECT = 'Проверка отправки LocalOS'
EMAIL = r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+'


def matches(message):
    return bool(re.search(r'(?:контрольн\w*|тестов\w*)\s+письм', message, re.I))


def digest(data):
    keys = ('business_id', 'user_id', 'sender_account_id', 'sender', 'recipient', 'subject', 'body')
    return hashlib.sha256(json.dumps({k: data.get(k) for k in keys}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _one(cursor):
    row = cursor.fetchone()
    if row is None:
        return {}
    if hasattr(row, 'keys'):
        return dict(row)
    return dict(zip([column[0] for column in cursor.description], row))


def parse(message):
    recipient = re.search(r'\bна\s+(' + EMAIL + r')', message, re.I)
    sender = re.search(r'\bот\s+(?:подключ[её]нного\s+)?(' + EMAIL + r')', message, re.I)
    if not recipient or not sender:
        raise ValueError('Укажите адрес получателя и подключённого отправителя: «на email от email».')
    subject = re.search(r'Тема:\s*[«"]([^»"]+)[»"]', message, re.I)
    body = re.search(r'Текст:\s*[«"]([^»"]+)[»"]', message, re.I)
    normalize = lambda text: re.sub(r'\s+', ' ', text).strip().rstrip('.!?…')
    if body and normalize(body[1]) != normalize(BODY):
        raise ValueError('Для контрольной проверки используйте текст: «' + BODY + '». Произвольные письма готовятся в партнёрской кампании.')
    result = {'recipient': recipient[1].lower(), 'sender': sender[1].lower(),
              'subject': subject[1].strip() if subject else SUBJECT, 'body': BODY}
    if result['recipient'] == result['sender']:
        raise ValueError('Адрес получателя должен отличаться от отправителя.')
    if '\n' in result['subject'] or '\r' in result['subject'] or len(result['subject']) > 120:
        raise ValueError('Укажите тему одной строкой, до 120 символов.')
    return result


def load_sender(cursor, *, business_id, user_id, sender, sender_account_id=None):
    # Re-read privileges on confirmation, never trust a model-provided actor flag.
    cursor.execute('SELECT is_superadmin FROM users WHERE id=%s', (user_id,))
    admin = bool(_one(cursor).get('is_superadmin'))
    cursor.execute('''SELECT id,scope_type,business_id,sender_identity,status,outreach_enabled,
        health_status,capabilities_json FROM outreach_sender_accounts
        WHERE channel='email' AND lower(sender_identity)=%s
        AND (business_id=%s OR (scope_type='platform' AND %s))
        AND (%s IS NULL OR id::text=%s) ORDER BY created_at LIMIT 2''',
        (sender, business_id, admin, sender_account_id, sender_account_id))
    rows = []
    while True:
        item = _one(cursor)
        if not item:
            break
        rows.append(item)
    if len(rows) != 1:
        raise ValueError('Подключённый отправитель не найден, недоступен или неоднозначен. Проверьте подключения.')
    account = rows[0]
    caps = account.get('capabilities_json') or {}
    if (account['status'] != 'connected' or not account.get('outreach_enabled')
            or account.get('health_status') in {'paused', 'blocked'}
            or not caps.get('direct_send') or not caps.get('reply_sync')):
        raise ValueError('Отправитель не готов к отправке и отслеживанию ответов. Проверьте подключение и разрешение.')
    return account


def preview(cursor, *, business_id, user_id, message):
    try:
        fields = parse(message)
        sender = load_sender(cursor, business_id=business_id, user_id=user_id, sender=fields['sender'])
    except ValueError as exc:
        return {'status': 'clarification_required', 'chat_response': str(exc), 'external_writes_performed': False}
    envelope = {**fields, 'business_id': business_id, 'user_id': user_id,
                'sender_account_id': str(sender['id'])}
    envelope['review_hash'] = digest(envelope)
    text = (f"Контрольное письмо\nОт: {fields['sender']}\nКому: {fields['recipient']}\n"
            f"Тема: {fields['subject']}\n\n{fields['body']}\n\n"
            'Одно письмо, без повторных касаний. Пока не отправлено. Подтвердите постановку в очередь.')
    return {'status': 'approval_required', 'chat_response': text,
            'approval': {'status': 'pending', 'capability': CAPABILITY, 'summary': text, 'envelope': envelope},
            'external_writes_performed': False}


def _create_campaign(cursor, *, fields, account, action_id, user_id):
    """Persist a noncommercial control fixture in the existing native model."""
    from services.outreach_personalization_ai import PROMPT_VERSION, REVIEW_PROMPT_VERSION
    from services.outreach_campaign_service import research_source_fact_fingerprint, record_campaign_event
    ids = {key: str(uuid.uuid5(uuid.NAMESPACE_URL, f'localos:control-email:{action_id}:{key}'))
           for key in ('lead', 'workstream', 'contact', 'research', 'campaign', 'touch')}
    business = fields['business_id']
    mode = 'localos_for_partner' if account['scope_type'] == 'platform' else 'partner_business'
    policy = {'sender_mode': mode, 'approval_mode': 'manual', 'daily_limit': 10,
              'stop_on_reply': True, 'automatic_followups': False, 'minimum_cadence_hours': 24,
              'control_event_key': action_id, 'control_review_hash': fields['review_hash'],
              'represented_business_id': business}
    evidence = {'purpose': 'control_email', 'source': 'explicit_user_request', 'recipient': fields['recipient']}
    research = {'evidence_json': evidence, 'signals_json': [], 'report_hash': fields['review_hash']}
    now = datetime.now(timezone.utc).isoformat()
    brief = {'source': 'explicit_user_request', 'control_event_key': action_id,
             'generation_source': 'manual_product_correction',
             'generation_prompt_version': PROMPT_VERSION, 'semantic_review_prompt_version': REVIEW_PROMPT_VERSION,
             'source_fact_fingerprint': research_source_fact_fingerprint(research),
             'manual_edit_reviewed_by': user_id, 'manual_edit_reviewed_at': now,
             'manual_edit_review_passed': True, 'manual_edit_review_required': False}
    gate = {'passed': True, 'verdict': 'approve', 'blocking_reasons': [],
            'manual_review': {'passed': True, 'review_version': REVIEW_PROMPT_VERSION,
                              'source': 'explicit_control_email_confirmation', 'reviewed_at': now,
                              'checks': ['exact_review_hash', 'fixed_noncommercial_control_text', 'one_touch_only']}}
    cursor.execute('''INSERT INTO prospectingleads
        (id,name,email,source,status,pipeline_status,intent,business_id,created_at,updated_at)
        VALUES (%s,%s,%s,'control_email','new','unprocessed','control_email',%s,NOW(),NOW())''',
        (ids['lead'], 'Контрольное письмо · ' + fields['recipient'], fields['recipient'], business))
    cursor.execute('''INSERT INTO lead_workstreams
        (id,lead_id,workstream_type,client_business_id,status,created_by,created_at,updated_at)
        VALUES (%s,%s,%s,%s,'unprocessed',%s,NOW(),NOW())''',
        (ids['workstream'], ids['lead'], 'client_partnership', business, user_id))
    cursor.execute('''INSERT INTO lead_contact_points
        (id,lead_id,contact_type,value,normalized_value,owner_type,source_type,provider,confidence,
         verification_status,verified_at,created_at,updated_at)
        VALUES (%s,%s,'email',%s,%s,'person','user_input','user',1,'confirmed_source',NOW(),NOW(),NOW())''',
        (ids['contact'], ids['lead'], fields['recipient'], fields['recipient']))
    cursor.execute('''INSERT INTO lead_workstream_research
        (id,workstream_id,score,qualification_stage,signal_label,score_breakdown,signals_json,sources_json,
         contact_evidence_json,limitations_json,message_brief_json,message_readiness_json,report_hash,evidence_json,researched_at,created_at)
        VALUES (%s,%s,0,'potential_fit','fit_only','{}','[]','[]','[]','[]',%s,'{}',%s,%s,NOW(),NOW())''',
        (ids['research'], ids['workstream'], Json(brief), fields['review_hash'], Json(evidence)))
    cursor.execute('''INSERT INTO outreach_campaigns
        (id,workstream_id,lead_id,scope_type,business_id,version,status,sender_mode,selected_offer_json,
         decision_snapshot_json,policy_json,recipient_key,created_by,created_at,updated_at)
        VALUES (%s,%s,%s,%s,%s,1,'draft',%s,'{}','{}',%s,%s,%s,NOW(),NOW())''',
        (ids['campaign'], ids['workstream'], ids['lead'], 'business', business, mode,
         Json(policy), 'lead:' + ids['lead'], user_id))
    cursor.execute('''INSERT INTO outreach_campaign_touches
        (id,campaign_id,sequence_index,channel,contact_point_id,sender_account_id,angle_type,scheduled_at,
         status,subject,generated_text,message_brief_json,quality_gate_json,created_at,updated_at)
        VALUES (%s,%s,1,'email',%s,%s,'control_email',NOW(),'draft',%s,%s,%s,%s,NOW(),NOW())''',
        (ids['touch'], ids['campaign'], ids['contact'], str(account['id']), fields['subject'], fields['body'], Json(brief), Json(gate)))
    record_campaign_event(cursor, ids['campaign'], 'control_email_reviewed', actor_id=user_id,
                          payload={'operator_action_id': action_id, 'review_hash': fields['review_hash'], 'followups': False})
    return ids['campaign']


def execute(cursor, *, business_id, user_id, envelope, action_id):
    if (envelope.get('business_id') != business_id or envelope.get('user_id') != user_id
            or envelope.get('review_hash') != digest(envelope) or envelope.get('body') != BODY):
        return {'status': 'blocked', 'chat_response': 'Условия письма изменились. Подготовьте новый просмотр.',
                'blocked_reasons': ['control_email_review_changed']}
    try:
        account = load_sender(cursor, business_id=business_id, user_id=user_id, sender=envelope['sender'],
                              sender_account_id=envelope['sender_account_id'])
    except ValueError as exc:
        return {'status': 'blocked', 'chat_response': str(exc), 'blocked_reasons': ['control_email_sender_unavailable']}
    # Native approval services need dict rows; share the caller's transaction.
    native = cursor.connection.cursor(cursor_factory=RealDictCursor)
    native.execute('SAVEPOINT control_email_prepare')
    try:
        campaign_id = _create_campaign(native, fields=envelope, account=account, action_id=action_id, user_id=user_id)
        from services.outreach_campaign_service import approve_campaign
        approve_campaign(native, campaign_id, user_id=user_id)
        native.execute('RELEASE SAVEPOINT control_email_prepare')
    except (ValueError, LookupError) as exc:
        native.execute('ROLLBACK TO SAVEPOINT control_email_prepare')
        native.execute('RELEASE SAVEPOINT control_email_prepare')
        return {'status': 'blocked', 'chat_response': 'Письмо не поставлено в очередь: ' + str(exc),
                'blocked_reasons': ['control_email_preflight_failed']}
    finally:
        native.close()
    return {'status': 'completed', 'chat_response': 'Контрольное письмо поставлено в очередь. Это ещё не подтверждение отправки. Повторных касаний нет.',
            'campaign_id': campaign_id, 'delivery_status': 'queued', 'external_writes_performed': False,
            'result_ref': {'entity_id': campaign_id, 'href': '/dashboard/partnerships?section=send&business_id=' + business_id, 'label': 'Проверить отправку'}}
