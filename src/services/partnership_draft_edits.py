"""Save a reviewed local draft without creating any delivery permission."""
from services.operator_conversations import _row
from services.outreach_draft_review import draft_review_digest


def save_draft(cursor, *, business_id, user_id, draft_id, text, expected_digest):
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    _, access=authorize_actor(cursor,user_id,business_id,require_write=True,check_subscription=False)
    if not capability_access_payload(access,'partnerships').get('allowed'):
        raise PermissionError('Нет доступа к партнёрствам.')
    if not isinstance(text,str) or not text.strip() or len(text)>10000:
        raise ValueError('Введите текст письма длиной до 10 000 символов.')
    cursor.execute('''SELECT d.*,l.email,l.selected_channel FROM outreachmessagedrafts d
        JOIN prospectingleads l ON l.id=d.lead_id
        WHERE d.id=%s AND (EXISTS(SELECT 1 FROM lead_workstreams w
            WHERE w.id=d.workstream_id AND w.client_business_id=%s AND w.workstream_type='client_partnership')
            OR (d.workstream_id IS NULL AND l.business_id=%s AND l.intent='partnership_outreach'))
        FOR UPDATE OF d,l''',(draft_id,business_id,business_id))
    draft=_row(cursor,cursor.fetchone())
    if not draft:raise PermissionError('Письмо недоступно в выбранном бизнесе.')
    if draft.get('status') not in {'generated','draft','edited','rejected'}:
        raise ValueError('Письмо уже утверждено или отправлено. Его нельзя менять как черновик.')
    origin = draft.get('learning_note_json') or {}
    if isinstance(origin, dict) and origin.get('campaign_id'):
        raise ValueError('Это письмо входит в кампанию. Откройте редактор кампании.')
    if not expected_digest or expected_digest!=draft_review_digest(draft):
        raise ValueError('Письмо или контакт изменился. Обновите список перед сохранением.')
    cursor.execute('''UPDATE outreachmessagedrafts SET edited_text=%s,approved_text=NULL,
        status='generated',updated_at=NOW() WHERE id=%s RETURNING id,status''',(text.strip(),draft_id))
    result=_row(cursor,cursor.fetchone())
    from psycopg2.extras import Json
    import uuid
    cursor.execute('''INSERT INTO agent_action_ledger(id,business_id,action_type,capability,risk_level,status,input_summary,metadata_json)
        VALUES(%s,%s,'partnership_draft_saved','partnerships.selected_draft','low','completed',
        'Draft saved without approval or dispatch',%s)''',(str(uuid.uuid4()),business_id,Json({'draft_id':draft_id,'user_id':user_id,'external_writes_performed':False})))
    return result
