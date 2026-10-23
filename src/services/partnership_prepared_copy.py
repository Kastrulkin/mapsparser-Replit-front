"""Human-authored partnership drafts. Preparation never grants delivery permission."""
import hashlib
import json
import re
import uuid
from psycopg2.extras import Json
from services.operator_conversations import _row


def save_human_draft(cursor, *, user_id, business_id, lead_id, text, channel=None, recipient=None):
    from services.operator_partner_work import partner_selection
    from services.outreach_safety_service import load_partnership_repeat_contact_guard
    selection=partner_selection(cursor,user_id=user_id,business_id=business_id,item_id=lead_id)
    if not isinstance(text,str) or not text.strip() or len(text)>10000:
        raise ValueError('Введите готовый текст письма до 10 000 символов.')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(f'partner-human-draft:{business_id}:{lead_id}',))
    cursor.execute('SELECT * FROM prospectingleads WHERE id=%s',(lead_id,));lead=_row(cursor,cursor.fetchone())
    guard=load_partnership_repeat_contact_guard(cursor,lead_id=lead_id,workstream_id=selection['workstream_id'])
    if guard.get('blocked') or guard.get('last_contact_at'):
        raise ValueError('С этой компанией уже общались или есть запрет. Первое холодное письмо не создано.')
    chosen=channel or selection['channel']
    if chosen=='manual':
        chosen='telegram' if lead.get('telegram_url') else 'email' if lead.get('email') else None
    if chosen not in {'telegram','email'}:
        raise ValueError('Для готового письма выберите Telegram или электронную почту.')
    contact=str((lead.get('telegram_url') if chosen=='telegram' else lead.get('email')) or '').strip()
    if not contact:raise ValueError('У партнёра нет контакта для выбранного канала.')
    def normalize(value):
        return str(value or '').lower().removeprefix('https://t.me/').removeprefix('http://t.me/').removeprefix('@').rstrip('/')
    if recipient and normalize(recipient)!=normalize(contact):
        raise ValueError('Получатель не совпадает с контактом выбранной компании. Сначала проверьте карточку.')
    from services.partnership_prepared_campaigns import cold_guard
    cold_guard(cursor,lead,selection['workstream_id'],contact)
    # Never overwrite approved copy, campaign versions, or a queued message.
    fingerprint=hashlib.sha256(json.dumps([business_id,lead_id,chosen,contact,text],ensure_ascii=False).encode()).hexdigest()
    cursor.execute("SELECT id,status,channel FROM outreachmessagedrafts WHERE lead_id=%s AND workstream_id=%s AND learning_note_json->>'human_copy_hash'=%s ORDER BY created_at DESC LIMIT 1",(lead_id,selection['workstream_id'],fingerprint))
    existing=_row(cursor,cursor.fetchone())
    if existing:return {**existing,'reused':True}
    draft_id=str(uuid.uuid4())
    cursor.execute('''INSERT INTO outreachmessagedrafts(id,lead_id,workstream_id,channel,angle_type,tone,status,generated_text,learning_note_json,created_by,include_room_link,created_at,updated_at)
        VALUES(%s,%s,%s,%s,'human_first_note','human','generated',%s,%s,%s,FALSE,NOW(),NOW()) RETURNING id,status,channel''',
        (draft_id,lead_id,selection['workstream_id'],chosen,text,Json({'human_copy_hash':fingerprint,'source':'human_supplied_copy','recipient':contact,'content_review_required':True,'delivery_authorized':False}),user_id))
    result=_row(cursor,cursor.fetchone())
    cursor.execute("INSERT INTO agent_action_ledger(id,business_id,action_type,capability,risk_level,status,input_summary,metadata_json) VALUES(%s,%s,'partnership_human_draft_created','partnerships.selected_draft','low','completed','Saved exact human copy; no approval or delivery',%s)",(str(uuid.uuid4()),business_id,Json({'draft_id':draft_id,'lead_id':lead_id,'user_id':user_id,'external_writes_performed':False})))
    return result
