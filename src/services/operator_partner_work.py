"""Business-scoped partner selection and the existing first-note queue."""
import hashlib
import inspect
import json
import re
import uuid
from datetime import datetime
from email.utils import parsedate_to_datetime

from services.operator_conversations import _row

CHANNEL_LABELS = {'email': 'Эл. почта', 'telegram': 'Telegram', 'max': 'MAX', 'vk': 'VK', 'whatsapp': 'WhatsApp', 'manual': 'Канал нужно выбрать'}
PARTNER_STATUS_LABELS = {'new': 'Новый', 'imported': 'Добавлен', 'draft_ready': 'Письмо подготовлено', 'contacted': 'Связались', 'replied': 'Ответил', 'converted': 'Стали партнёрами'}
DRAFT_STATUS_LABELS = {'draft': 'Черновик', 'generated': 'Черновик', 'edited': 'Отредактирован', 'approved': 'Утверждено', 'sent': 'Отправлено', 'delivered': 'Доставлено', 'rejected': 'Нужны правки', 'failed': 'Ошибка отправки'}


def partner_selection(cursor, *, user_id, business_id, item_id, expected_updated_at=None):
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    _, access = authorize_actor(cursor, user_id, business_id, check_subscription=False, require_write=True)
    if not capability_access_payload(access, 'partnerships').get('allowed'):
        raise PermissionError('Партнёрства недоступны. Проверьте доступ выбранного бизнеса.')
    uuid.UUID(str(item_id))
    cursor.execute("""SELECT l.id,l.business_id,l.name,l.city,l.category,l.status,
        COALESCE(ws.selected_channel,l.selected_channel) selected_channel,
        l.email,l.phone,l.telegram_url,l.whatsapp_url,l.website,l.updated_at,
        ws.id workstream_id,ws.status workstream_status,ws.updated_at workstream_updated_at
        FROM prospectingleads l JOIN lead_workstreams ws ON ws.lead_id=l.id
        WHERE l.id=%s AND ws.client_business_id=%s
        AND ws.workstream_type='client_partnership'""", (str(item_id), business_id))
    leads = [_row(cursor, row) for row in cursor.fetchall()]
    if len(leads) != 1:
        raise PermissionError('Партнёр недоступен или его контекст неоднозначен. Откройте карточку из списка заново.')
    lead = leads[0]
    if not lead:
        raise PermissionError('Партнёр недоступен в выбранном бизнесе.')
    if expected_updated_at:
        current = datetime.fromisoformat(str(lead.get('updated_at')).replace('Z', '+00:00'))
        try:
            seen = datetime.fromisoformat(str(expected_updated_at).replace('Z', '+00:00'))
        except ValueError:
            # Flask's legacy JSON date loses microseconds; the approval still binds
            # the complete row, including exact timestamp and recipient contacts.
            seen = parsedate_to_datetime(str(expected_updated_at))
            current = current.replace(microsecond=0)
        if seen != current:
            raise ValueError('Карточка партнёра изменилась. Откройте актуальную версию.')
    version = hashlib.sha256(json.dumps(lead, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
    return {'item_id': str(lead['id']), 'workstream_id': str(lead['workstream_id']), 'version': version, 'name': str(lead.get('name') or 'Партнёр'),
            'channel': str(lead.get('selected_channel') or 'manual'), 'status': str(lead.get('status') or '')}


def queue_first_note(cursor, *, user_id, business_id, lead_id, workstream_id=None, expected_version=None, allow_paid_enrichment=False):
    selection = partner_selection(cursor, user_id=user_id, business_id=business_id, item_id=lead_id)
    if expected_version and selection['version'] != expected_version:
        raise ValueError('Карточка или контакт партнёра изменились. Проверьте действие заново.')
    if selection['status'] in {'archived', 'deleted', 'do_not_contact', 'declined', 'refused'}:
        raise ValueError('Подготовка письма для этого статуса партнёра недоступна.')
    from services.lead_workstream_service import resolve_workstream
    from services.contact_intelligence_service import enqueue_enrichment_job
    workstream = resolve_workstream(cursor.connection, lead_id=lead_id, workstream_id=workstream_id or selection['workstream_id'],
        expected_type='client_partnership', client_business_id=business_id)
    # A confirmed new request may retry a terminal failed preparation. Reuse
    # active/successful work; the same advisory lock prevents parallel retries.
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (f"lead-enrichment:{workstream['id']}",))
    cursor.execute('SELECT status FROM lead_enrichment_jobs WHERE workstream_id=%s ORDER BY created_at DESC LIMIT 1',
                   (str(workstream['id']),))
    previous = _row(cursor, cursor.fetchone())
    options = {'allow_paid_enrichment': allow_paid_enrichment,
               'force': previous.get('status') in {'failed', 'needs_evidence', 'needs_contact'}}
    # Preserve actor attribution in the newer queue already deployed on production.
    if 'requested_by_user_id' in inspect.signature(enqueue_enrichment_job).parameters:
        options['requested_by_user_id'] = user_id
    job = enqueue_enrichment_job(cursor, str(workstream['id']), **options)
    return {'id': str(job['id']), 'status': str(job.get('status') or 'queued'),
            'phase': job.get('current_phase'), 'reused': bool(job.get('reused'))}


def route(cursor, *, user_id, business_id, message, selected, conversation_id=None):
    current = partner_selection(cursor, user_id=user_id, business_id=business_id, item_id=selected.get('item_id'))
    text = str(message or '').strip().lower()
    if current['version'] != selected.get('version') and re.search(r'подготов|напиши|составь|создай|новое письмо|отправ|разошл', text):
        raise ValueError('Карточка партнёра изменилась. Откройте её заново перед продолжением.')
    base = {'capability': 'partnerships.read', 'status': 'completed', 'external_writes_performed': False,
            'selected_partner': current}
    if re.fullmatch(r'(?:отмена|отмени|не надо|стоп|закончить обсуждение)[.!]?', text):
        if conversation_id:
            cursor.execute("UPDATE operatoractions SET status='rejected',updated_at=NOW() WHERE business_id=%s AND user_id=%s AND conversation_id=%s AND capability='partnerships.selected_draft' AND status IN ('pending','pending_approval')", (business_id, user_id, conversation_id))
        return {**base, 'status': 'cancelled', 'chat_response': 'Обсуждение партнёра закрыто.'}, {}
    pending = {'capability': 'partnerships.selected', 'selected_partner': current}
    if re.search(r'отправ|разошл|напомни', text):
        return {**base, 'chat_response': 'Откройте письмо в карточке партнёра: проверьте полный текст, контакт и канал, затем отдельно подтвердите отправку.'}, pending
    if re.search(r'подготов|напиши|составь|создай|новое письмо', text):
        return {**base, 'capability': 'partnerships.selected_draft', 'status': 'approval_required',
            'chat_response': f"Партнёр: {current['name']}. Проверим контакт и подготовим первое письмо в существующем процессе LocalOS. Работа использует действующие лимиты и бюджет. Платное обогащение выключено. Отправку письма нужно будет согласовать отдельно.",
            'approval': {'status': 'pending', 'envelope': {'capability': 'partnerships.selected_draft', 'business_id': business_id,
                'payload': {'lead_id': current['item_id'], 'version': current['version']}}}}, pending
    cursor.execute("""SELECT id,channel,status,generated_text,edited_text,approved_text FROM outreachmessagedrafts
        WHERE lead_id=%s AND workstream_id=%s
        ORDER BY updated_at DESC NULLS LAST,created_at DESC LIMIT 3""", (current['item_id'],current['workstream_id']))
    drafts = [_row(cursor, row) for row in cursor.fetchall()]
    parts = [f"Партнёр: {current['name']}. Канал: {CHANNEL_LABELS.get(current['channel'], 'Нужно выбрать')}. Статус: {PARTNER_STATUS_LABELS.get(current['status'], 'В работе')}."]
    for draft in drafts:
        body = str(draft.get('approved_text') or draft.get('edited_text') or draft.get('generated_text') or '')
        parts.append(f"Письмо · {CHANNEL_LABELS.get(draft.get('channel'), 'Канал нужно выбрать')} · {DRAFT_STATUS_LABELS.get(draft.get('status'), 'Проверьте статус')}\n{body}")
    if not drafts:
        parts.append('Писем пока нет. Напишите или надиктуйте «Подготовь первое письмо».')
    parts.append('Карточка партнёра открывается кнопкой возврата. Просмотр и обсуждение не отправляют письма.')
    return {**base, 'chat_response': '\n\n'.join(parts), 'drafts': drafts}, pending


def apply(cursor, *, user_id, business_id, envelope):
    payload = envelope.get('payload') or {}
    if not payload.get('version'):
        raise ValueError('Подтверждение устарело. Проверьте партнёра заново.')
    job = queue_first_note(cursor, user_id=user_id, business_id=business_id,
        lead_id=payload.get('lead_id'), expected_version=payload.get('version'))
    active = job['status'] in {'queued', 'collecting', 'verifying', 'researching', 'drafting', 'retry_wait'}
    ready = job['status'] == 'ready'
    text = ('Подготовка первого письма запущена. Результат появится в карточке партнёра.' if active else
            'Письмо подготовлено. Откройте карточку партнёра, чтобы проверить текст.' if ready else
            'Письмо пока не подготовлено. Откройте карточку партнёра: там указано, что нужно уточнить.')
    return {'status': 'queued' if active else 'completed' if ready else 'clarification_required',
            'capability': 'partnerships.selected_draft', 'preparation_job': job,
            'external_writes_performed': False, 'chat_response': text + ' Письмо не отправлено.'}
