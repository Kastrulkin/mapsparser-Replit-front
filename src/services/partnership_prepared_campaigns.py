"""Prepare exact human copy through canonical campaigns; never enroll or dispatch."""
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from psycopg2.extras import Json
from services.operator_conversations import _row

COPY_ONLY_REASONS={'DECORATIVE_PERSONALIZATION','WEAK_OFFER_BRIDGE','STYLE_VIOLATION','MANUAL_EDIT_REQUIRES_REVIEW'}


def validate_item(item):
    if not isinstance(item,dict):raise ValueError('Нужен объект готового обращения.')
    if item.get('channel') not in {'telegram','email'}:raise ValueError('Выберите Telegram или почту.')
    if not isinstance(item.get('lead_id'),str) or not item['lead_id']:raise ValueError('Выберите компанию.')
    for key in ['contact','source','observation']:
        if not isinstance(item.get(key),str) or not item[key].strip() or len(item[key])>3000:raise ValueError('Укажите контакт, источник и проверенный факт о компании.')
    try:
        observed=datetime.fromisoformat(str(item.get('observed_at') or '').replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-observed).total_seconds()
        if age<0 or age>30*86400:raise ValueError()
    except (ValueError,TypeError):raise ValueError('Укажите дату проверки источника за последние 30 дней.')
    if len(str(item.get('group') or ''))>200:raise ValueError('Название подборки слишком длинное.')
    u=urlparse(item['source'])
    if u.scheme not in {'http','https'} or not u.hostname or u.username or u.password:raise ValueError('Нужна публичная ссылка на источник.')
    touches=item.get('touches')
    if not isinstance(touches,list) or not 1<=len(touches)<=4:raise ValueError('Добавьте от одного до четырёх касаний.')
    last=-1
    for touch in touches:
        if not isinstance(touch,dict) or not isinstance(touch.get('text'),str) or not touch['text'].strip() or len(touch['text'])>3000:raise ValueError('Текст каждого касания должен содержать до 3000 знаков.')
        day=touch.get('day_offset')
        if not isinstance(day,int) or isinstance(day,bool) or day<0 or day>90 or day<=last or last==-1 and day!=0:raise ValueError('Первое касание — день 0, следующие — по возрастанию до 90 дней.')
        last=day
        subject=touch.get('subject') or ''
        if not isinstance(subject,str) or len(subject)>200 or '\n' in subject or '\r' in subject or item['channel']=='email' and not subject.strip():raise ValueError('Укажите корректную тему письма.')
    return item


def normalized(value):
    return str(value or '').strip().lower().removeprefix('https://t.me/').removeprefix('http://t.me/').removeprefix('@').rstrip('/')


def cold_guard(cursor,lead,workstream_id,contact):
    from services.outreach_safety_service import load_partnership_repeat_contact_guard
    guard=load_partnership_repeat_contact_guard(cursor,lead_id=str(lead['id']),workstream_id=workstream_id)
    if guard.get('blocked') or guard.get('last_contact_at'):
        raise ValueError('Есть прежнее общение или запрет. Компания исключена из первого обращения.')
    cursor.execute('''SELECT l.id FROM prospectingleads l WHERE
        (l.company_id IS NOT NULL AND l.company_id=%s OR lower(trim(l.email))=%s OR
         lower(trim(both '/' from replace(replace(replace(coalesce(l.telegram_url,''),'https://t.me/',''),'http://t.me/',''),'@','')))=%s)
        AND (l.last_contact_at IS NOT NULL OR EXISTS(SELECT 1 FROM lead_workstreams w WHERE w.lead_id=l.id AND w.last_contact_at IS NOT NULL)
          OR EXISTS(SELECT 1 FROM outreachsendqueue q WHERE q.lead_id=l.id)) LIMIT 1''',(lead.get('company_id'),normalized(contact),normalized(contact)))
    if cursor.fetchone():raise ValueError('Найдены прежние касания или очередь по компании/контакту. Первое обращение заблокировано.')
    from services.outreach_campaign_service import _suppression_status
    business_id=lead.get('business_id')
    if not business_id:raise ValueError('Не определён бизнес для проверки исключений из отправки.')
    suppression=_suppression_status(cursor,{'lead_id':str(lead['id']),'workstream_type':'client_partnership','client_business_id':business_id})
    if suppression.get('suppressed'):raise ValueError('Компания исключена из отправки. Откройте карточку и проверьте причину в разделе «Исключения из контактов».')


def prepare(cursor,*,business_id,user,item):
    from services.operator_partner_work import partner_selection
    from services.contact_intelligence_service import upsert_contact_points,verify_contact_points,build_native_research_payload
    from services.prospecting_research_service import _insert_research
    from services.outreach_campaign_service import build_preview,persist_preview
    from core.card_audit import build_lead_card_preview_snapshot
    from api import admin_prospecting as legacy
    validate_item(item)
    if not user.get('is_superadmin'):raise PermissionError('Использование общего отправителя LocalOS доступно администратору. Подготовьте письмо с аккаунтом бизнеса.')
    actor=str(user.get('user_id') or user.get('id') or '')
    selection=partner_selection(cursor,user_id=actor,business_id=business_id,item_id=item['lead_id'])
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(f'partner-prepared:{business_id}:{item["lead_id"]}',))
    cursor.execute('SELECT * FROM prospectingleads WHERE id=%s',(item['lead_id'],));lead=_row(cursor,cursor.fetchone())
    expected=lead.get('telegram_url') if item['channel']=='telegram' else lead.get('email')
    if normalized(expected)!=normalized(item['contact']):raise ValueError('Контакт изменился или принадлежит другой компании. Обновите карточку.')
    cold_guard(cursor,lead,selection['workstream_id'],item['contact'])
    fingerprint=hashlib.sha256(json.dumps([business_id,item],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    cursor.execute("SELECT id,status FROM outreach_campaigns WHERE workstream_id=%s AND policy_json->>'human_copy_hash'=%s ORDER BY version DESC LIMIT 1",(selection['workstream_id'],fingerprint))
    prior=_row(cursor,cursor.fetchone())
    if prior:return {**prior,'reused':True}
    history_receipt=check_provider_history(cursor,item)
    cursor.execute("SELECT id FROM outreach_campaigns WHERE workstream_id=%s AND status NOT IN ('draft','cancelled','completed','failed') LIMIT 1",(selection['workstream_id'],))
    if cursor.fetchone():raise ValueError('По этой компании уже есть действующая цепочка. Откройте её вместо нового запуска.')
    source_host=urlparse(item['source']).hostname or ''
    official_host=urlparse(str(lead.get('website') or '')).hostname or ''
    upsert_contact_points(cursor,str(lead['id']),[{'contact_type':item['channel'],'value':item['contact'],'owner_type':'company','source_url':item['source'],'source_type':'official_website' if source_host.removeprefix('www.')==official_host.removeprefix('www.') else 'saved_public_research','provider':'human_prepared_copy','confidence':0.7,'verification_status':'found'}])
    verify_contact_points(cursor,str(lead['id']),lead.get('website'))
    cursor.execute("SELECT id FROM lead_contact_points WHERE lead_id=%s AND contact_type=%s AND verification_status NOT IN ('invalid','stale') AND (lower(value)=%s OR lower(normalized_value)=%s) ORDER BY updated_at DESC LIMIT 1",(str(lead['id']),item['channel'],str(item['contact']).lower(),normalized(item['contact'])))
    cp=_row(cursor,cursor.fetchone())
    if not cp:raise ValueError('Не найден пригодный контакт. Проверьте получателя.')
    cursor.execute('UPDATE lead_workstreams SET selected_contact_point_id=%s WHERE id=%s',(cp['id'],selection['workstream_id']))
    audit=legacy._to_json_compatible(build_lead_card_preview_snapshot(lead))
    match=legacy._compute_partnership_match_result(cursor,business_id=business_id,lead_id=str(lead['id']),audit_json=audit,allow_external=False)
    legacy._save_partnership_match_assessment(cursor,lead_id=str(lead['id']),audit_json=audit,match_result=match)
    ws={'id':selection['workstream_id'],'workstream_type':'client_partnership','client_business_id':business_id}
    research=build_native_research_payload(lead,ws,{'imported_by':actor,'public_research_facts':[{'fact':item['observation'],'source_url':item['source'],'observed_at':item.get('observed_at'),'basis':'Сохранённое исследование, готовый текст предоставлен пользователем.'}]})
    _insert_research(cursor,selection['workstream_id'],{'score':research['score'],'qualification_stage':research['qualification_stage'],'signal_label':research['signal_label'],'score_breakdown':research['score_breakdown'],'why_now':research['why_now'],'signals':research['signals_json'],'sources':research['sources_json'],'contact_evidence':[],'suggested_opener':'','opener_source_url':item['source'],'limitations':research['limitations_json'],'message_brief':research['message_brief_json'],'report_hash':research['report_hash']},None)
    preview=build_preview(cursor,selection['workstream_id'],sender_mode='localos_for_partner',generate_ai=False,preserve_manual_text=True,manual_reviewer_role='superadmin',sequence=[{'channel':item['channel'],'angle':angle,'day_offset':t['day_offset']} for angle,t in zip(['signal','matching_authority','proof','final'],item['touches'])],touch_overrides=[{'sequence_index':i,'subject':t.get('subject') or '', 'text':t['text'],'original_text':t['text'],'original_subject':t.get('subject') or '', 'human_edited':True} for i,t in enumerate(item['touches'])])
    touches=preview.get('touches') or []
    if len(touches)!=len(item['touches']):raise ValueError('Подготовка остановлена: '+', '.join(preview.get('missing') or (preview.get('decision') or {}).get('reason_codes') or [preview.get('status','нет касаний')]))
    for a,b in zip(touches,item['touches']):
        bind_exact_copy(a,b,item['channel'])
        if str(a.get('sender_account_id') or '')!=history_receipt['sender_account_id']:raise ValueError('Изменился отправитель. Историю нужно проверить для выбранного аккаунта.')
        if a['channel_status']!='ready':raise ValueError('Канал или отправитель пока не готов: '+a['channel_status'])
    campaign=persist_preview(cursor,preview,user_id=actor)
    cursor.execute("UPDATE outreach_campaigns SET policy_json=policy_json || %s WHERE id=%s",(Json({'human_copy_hash':fingerprint,'human_copy_review_required':True,'prepared_group':str(item.get('group') or 'Первое обращение'),'delivery_authorized':False,'provider_history':history_receipt}),campaign['id']))
    return {**campaign,'touch_count':len(touches),'readiness':'needs_manual_review'}



def check_source_freshness(cursor,workstream_id,touches):
    from services.outreach_campaign_service import current_outreach_source_fact_fingerprint
    current=current_outreach_source_fact_fingerprint(cursor,workstream_id,'localos_for_partner')
    if not current or not touches or any(str((t.get('message_brief_json') or {}).get('source_fact_fingerprint') or '')!=current for t in touches):
        raise ValueError('Сведения о компании обновились после подготовки писем. Сохраните касания заново по актуальным сведениям; прежние тексты останутся в истории.')


def review_copy(cursor,*,business_id,user,campaign_id,digest):
    from services.operator_audio import authorize_actor
    from services.outreach_campaign_service import apply_draft_campaign_review
    from services.outreach_personalization_ai import REVIEW_PROMPT_VERSION
    from subscription_manager import capability_access_payload
    _,access=authorize_actor(cursor,str(user.get('user_id') or user.get('id')),business_id,require_write=True,check_subscription=False)
    if not capability_access_payload(access,'partnerships').get('allowed'):raise PermissionError('Нет доступа к партнёрствам.')
    cursor.execute("SELECT c.*,l.company_id FROM outreach_campaigns c JOIN prospectingleads l ON l.id=c.lead_id WHERE c.id=%s AND c.business_id=%s AND c.scope_type='business' AND c.status='draft' AND c.policy_json->>'human_copy_hash' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM outreach_campaigns newer WHERE newer.workstream_id=c.workstream_id AND newer.version>c.version) FOR UPDATE",(campaign_id,business_id))
    c=_row(cursor,cursor.fetchone())
    if not c:raise ValueError('Цепочка недоступна для проверки или уже изменилась.')
    touches=load_touches(cursor,campaign_id)
    if copy_digest(touches)!=digest:raise ValueError('Текст или получатель изменился. Откройте касания заново.')
    cold_guard(cursor,{'id':c['lead_id'],'company_id':c.get('company_id'),'business_id':business_id},str(c['workstream_id']),str(touches[0].get('recipient') or ''))
    check_source_freshness(cursor,str(c['workstream_id']),touches)
    reviewed=[]
    for touch in touches:
        gate=dict(touch.get('quality_gate_json') or {})
        if not set(gate.get('reason_codes') or []).issubset(COPY_ONLY_REASONS):raise ValueError('Есть ошибки фактов, получателя или безопасности. Сначала устраните их.')
        # This is an explicit human decision over exact saved copy, not a synthetic AI score.
        gate.update(passed=True,verdict='human_accepted',reason_codes=[],blocking_reasons=[],manual_review={'passed':True,'review_version':REVIEW_PROMPT_VERSION,'source':'explicit_saved_copy_review','reviewed_by':str(user.get('user_id') or user.get('id'))})
        gate.pop('criterion_scores',None);gate.pop('total_score',None);gate.pop('score',None)
        reviewed.append({'sequence_index':touch['sequence_index'],'text':touch.get('generated_text'),'subject':touch.get('subject'),'quality_gate':gate})
    result=apply_draft_campaign_review(cursor,campaign_id=campaign_id,reviewed_touches=reviewed,user_id=str(user.get('user_id') or user.get('id')))
    cursor.execute("UPDATE outreach_campaigns SET policy_json=policy_json || %s WHERE id=%s",(Json({'human_copy_review_required':False,'human_copy_reviewed_by':str(user.get('user_id') or user.get('id'))}),campaign_id))
    return result


def copy_digest(touches):
    return hashlib.sha256(json.dumps([{k:str(t.get(k) or '') for k in ['id','channel','contact_point_id','recipient','contact_source','sender_account_id','sender_identity','subject','generated_text','updated_at']} for t in touches],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def list_prepared(cursor,*,business_id,user_id):
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    _,access=authorize_actor(cursor,user_id,business_id,check_subscription=False)
    if not capability_access_payload(access,'partnerships').get('allowed'):raise PermissionError('Нет доступа к партнёрствам.')
    cursor.execute("SELECT DISTINCT ON(c.workstream_id) c.id,c.lead_id,c.workstream_id,c.status,c.policy_json,c.created_at,l.name,l.address,l.company_id FROM outreach_campaigns c JOIN prospectingleads l ON l.id=c.lead_id WHERE c.business_id=%s AND c.scope_type='business' AND c.policy_json->>'human_copy_hash' IS NOT NULL ORDER BY c.workstream_id,c.version DESC",(business_id,))
    rows=[_row(cursor,r) for r in cursor.fetchall()]
    rows.sort(key=lambda row:str(row.get('created_at') or ''),reverse=True)
    for row in rows:
        touches=load_touches(cursor,row['id']);row['review_digest']=copy_digest(touches)
        row['touches']=[{k:t.get(k) for k in ['id','sequence_index','channel','subject','generated_text','recipient','contact_source','sender_name','sender_identity','scheduled_at','status']} for t in touches]
        try:
            cold_guard(cursor,{'id':row['lead_id'],'company_id':row.get('company_id'),'business_id':business_id},str(row['workstream_id']),str(touches[0].get('recipient') or '') if touches else '')
            if row['status']=='draft':check_source_freshness(cursor,str(row['workstream_id']),touches)
        except ValueError as e:row['hold_reason']=str(e)
        row['needs_review']=bool((row.get('policy_json') or {}).get('human_copy_review_required'))
    return rows


def load_touches(cursor,campaign_id):
    cursor.execute('''SELECT t.*,cp.value recipient,cp.source_url contact_source,COALESCE(NULLIF(s.display_name,''),NULLIF(s.sender_identity,''),CASE WHEN s.id IS NOT NULL AND s.channel='telegram' THEN 'Подключённый Telegram LocalOS' END) sender_name,s.sender_identity FROM outreach_campaign_touches t LEFT JOIN lead_contact_points cp ON cp.id=t.contact_point_id LEFT JOIN outreach_sender_accounts s ON s.id=t.sender_account_id WHERE t.campaign_id=%s ORDER BY t.sequence_index''',(campaign_id,))
    return [_row(cursor,r) for r in cursor.fetchall()]


def check_provider_history(cursor,item):
    """Reuse existing connected adapters, read only; unknown history is never empty history."""
    channel=item['channel']
    cursor.execute("SELECT * FROM outreach_sender_accounts WHERE scope_type='platform' AND channel=%s AND status='connected' AND health_status='healthy' AND outreach_enabled=TRUE ORDER BY updated_at DESC",(channel,))
    senders=[_row(cursor,r) for r in cursor.fetchall()]
    if channel=='telegram':
        from services.telegram_account_permissions_service import assert_account_access
        from core.telegram_userbot import load_userbot_account,inspect_telegram_entity,fetch_message_page
        sender=next((s for s in senders if assert_account_access(cursor,s['external_account_id'],business_id=None,scope_type='platform',capability='outreach')[0]),None)
        if not sender:raise ValueError('Нет готового Telegram-отправителя с разрешением на аутрич.')
        auth=load_userbot_account(cursor,business_id=None,account_id=sender['external_account_id'])
        if not auth:raise ValueError('Telegram-отправитель требует переподключения.')
        entity=inspect_telegram_entity(auth,item['contact'])
        if entity.get('status')!='ok' or not entity.get('recipient_eligible'):raise ValueError('Этот Telegram ведёт в бота, канал или недоступный аккаунт. Нужен контакт для личного сообщения.')
        page=fetch_message_page(auth,item['contact'],limit=1)
        if page.get('status')!='ok':raise ValueError('Не удалось проверить историю Telegram. Контакт не считается новым.')
        if page.get('messages'):raise ValueError('В Telegram уже есть переписка с этим получателем. Компания не включена в первое обращение.')
    else:
        from services.outreach_email_adapter import fetch_complete_mailbox_window,EmailAdapterError
        # The connected enabled platform mailbox is selected by the native availability resolver as well.
        sender=next((s for s in senders if str(s.get('sender_identity') or '').lower()=='localosgo@gmail.com'),None)
        if not sender:raise ValueError('Не найдена подключённая почта LocalOS для проверки истории.')
        for folder in ['sent','all']:
            for attempt in range(2):
                try:
                    value=fetch_complete_mailbox_window(sender,mailbox=folder,since_at=datetime(2000,1,1,tzinfo=timezone.utc),until_at=datetime.now(timezone.utc),recipient_emails=[item['contact']],max_messages=20000,timeout=45,total_timeout=120)
                    break
                except EmailAdapterError as error:
                    if attempt==0 and error.retryable:continue
                    raise ValueError('Почта не завершила проверку прежней переписки. Ничего не отправлено. Повторите сохранение позже; контакт пока не считается новым.') from error
            if value.get('messages'):raise ValueError('В почте найдена прежняя переписка или уведомление о недоставке. Компания не включена в первое обращение.')
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'sender_account_id':str(sender['id']),'channel':channel,'message_count':0,'complete':True}


def enqueue_preparation(cursor,*,business_id,user,item):
    from services.operator_partner_work import partner_selection
    from services.operator_async_jobs import create_operator_async_job
    validate_item(item)
    if not user.get('is_superadmin'):raise PermissionError('Использование общего отправителя LocalOS доступно администратору.')
    actor=str(user.get('user_id') or user.get('id') or '')
    partner_selection(cursor,user_id=actor,business_id=business_id,item_id=item['lead_id'])
    key=hashlib.sha256(json.dumps([business_id,item],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    job=create_operator_async_job(cursor,user_id=actor,action_id=None,business_id=business_id,kind='partner_copy_prepare',payload={'item':item},idempotency_key='partner-copy:'+key,stage='Проверяем переписку и сохраняем готовые касания',max_attempts=3)
    if job['status']=='failed':
        from services.operator_async_jobs import retry_operator_async_job
        job=retry_operator_async_job(cursor,job_id=job['id'],user_id=actor,scope={'kind':'business','business_ids':[business_id]},is_superadmin=False)
    return job


def preparation_status(cursor,*,business_id,user_id,job_id):
    from services.operator_async_jobs import load_operator_async_job
    job=load_operator_async_job(cursor,job_id=job_id,user_id=user_id,scope={'kind':'business','business_ids':[business_id]},is_superadmin=False)
    if not job or job['kind']!='partner_copy_prepare' or job['business_id']!=business_id:raise PermissionError('Проверка недоступна в этом бизнесе.')
    return job


def process_preparation_job(job):
    from database_manager import DatabaseManager
    from services.operator_audio import authorize_actor
    db=DatabaseManager()
    try:
        cursor=db.conn.cursor()
        actor,_=authorize_actor(cursor,str(job['user_id']),str(job['business_id']),check_subscription=False,require_write=True)
        result=prepare(cursor,business_id=str(job['business_id']),user={'user_id':str(job['user_id']),'is_superadmin':actor['is_superadmin']},item=job['payload_json']['item'])
        db.conn.commit()
        return {k:result.get(k) for k in ['id','status','touch_count','reused']}
    except Exception:
        db.conn.rollback();raise
    finally:db.close()


def list_preparation_jobs(cursor,*,business_id,user_id):
    cursor.execute("SELECT id,status,stage,error_text FROM operator_async_jobs WHERE user_id=%s AND business_id=%s AND kind='partner_copy_prepare' AND status IN ('queued','running') ORDER BY created_at DESC LIMIT 50",(user_id,business_id))
    return [_row(cursor,row) for row in cursor.fetchall()]


def bind_exact_copy(preview_touch,human_touch,channel):
    if preview_touch['text']!=human_touch['text']:
        raise ValueError('Текст изменился при подготовке. Ничего не сохранено.')
    if channel=='email':
        if preview_touch.get('subject','')!=human_touch.get('subject',''):
            raise ValueError('Тема письма изменилась при подготовке. Ничего не сохранено.')
    else:
        # The native builder supplies an email-style subject for every channel.
        # Telegram sends the body only; never display its unused generated subject.
        preview_touch['subject']=''
