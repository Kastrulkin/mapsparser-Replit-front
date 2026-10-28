"""Free, source-bound template drafts. No LLM, search, reservation or send.

Template content is imported from the existing project artefacts, never from a
rendered batch. Saved campaigns remain drafts requiring native manual review.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime, timezone
from psycopg2.extras import Json

ROOT = Path(__file__).with_name('outreach_templates')
RIDERRA = 'edbd961a-273f-4f15-836e-33aacc0aa0e3'
DEFINITIONS = {
    'phuket': ('riderra-phuket.json', 'Riderra · Пхукет', 'Phuket', 'riderracs@gmail.com'),
    'la': ('riderra-la.json', 'Riderra · Лос-Анджелес', 'Los Angeles', 'riderracs@gmail.com'),
    'localos': ('localos-partner.json', 'LocalOS · партнёрство', None, 'localosgo@gmail.com'),
}
UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


def definition(key):
    if key not in DEFINITIONS:
        raise ValueError('template_unknown')
    value = json.loads((ROOT / DEFINITIONS[key][0]).read_text())
    return {**value, 'key': key, 'label': DEFINITIONS[key][1],
            'sha256': hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}


def request(message):
    text = str(message or '').strip()
    if not re.search(r'шаблон', text, re.I) or not re.search(r'письм|черновик|шаблоны|пхукет|phuket|лос.анджелес|localos|локалос|\bla\b', text, re.I):
        return None
    ids = list(dict.fromkeys(re.findall(UUID, text, re.I)))
    if len(ids) > 1:
        return {'operation': 'invalid'}
    keys = [key for key, pattern in [('phuket',r'пхукет|phuket'),('la',r'лос.анджелес|\bla\b'),('localos',r'localos|локалос')] if re.search(pattern,text,re.I)]
    if len(keys) > 1:
        return {'operation': 'invalid'}
    operation = 'save' if re.match(r'\s*сохран',text,re.I) else 'preview'
    if not keys:
        operation = 'list'
    result={'operation': operation, 'template': keys[0] if keys else None,
            'task_id': ids[0] if ids else None}
    if re.search(r'карточк',text,re.I):
        result['workstream_id']=result.pop('task_id')
    return result


def sourced_company(name, evidence):
    """SEO titles are not company names. Accept a title suffix only with domain proof."""
    name = str(name or '').strip()
    if not name or len(name)>160 or any(c in name for c in '\n\r{}'):
        raise ValueError('company_name_required')
    if re.search(r'\b(book|buy|best)\b|holiday packages',name,re.I):
        for item in evidence:
            fact = str(item.get('fact') or item.get('quote') or '')
            brand = fact.rsplit('|',1)[-1].strip() if '|' in fact else ''
            host = (urlsplit(str(item.get('source_url') or '')).hostname or '').split('.')
            if 2<=len(brand)<=60 and re.sub(r'[^a-z0-9]','',brand.lower()) in host:
                return brand
        raise ValueError('company_name_required')
    return name


def render(key, *, company, evidence, audience='', variant='A'):
    template=definition(key)
    if variant not in {'A','B'}: raise ValueError('template_variant_invalid')
    company=sourced_company(company,evidence)
    slots={'company':company}
    if key=='localos':
        observations=[str(e.get('fact') or '').strip() for e in evidence
                      if e.get('source_url') and e.get('fact') and e.get('kind') != 'contact']
        if not observations or not audience.strip(): raise ValueError('template_slots_missing')
        observation=observations[0]
        if re.search(r'[А-Яа-яЁё]', observation+' '+audience):
            raise ValueError('english_template_slots_required')
        slots.update(observation=observation, audience=audience.strip().rstrip('.'))
    if any(len(v)>700 or any(c in v for c in '\n\r{}') for v in slots.values()):
        raise ValueError('template_slots_invalid')
    body=(template.get('bodies') or {}).get(variant) or template.get('body')
    return {'subject':template['subject'].format(**slots),'body':body.format(**slots),
            'template':template,'slots':slots,'variant':variant}


def prices_current(cursor,key):
    if key=='localos': return None
    from services.riderra_template_authorization_service import load_pricebook_attestation
    cursor.execute("""SELECT id FROM outreach_sender_account_events WHERE
        event_type='provider_snapshot_verified' AND payload_json->>'snapshot_kind'='riderra_pricebook_snapshot'
        ORDER BY created_at DESC LIMIT 5""")
    ids=[str(r['id']) for r in cursor.fetchall()]
    expected = ([('Phuket town','Standard class car',3,'22,00','EUR'),
                 ('PaTong, Phuket','Standard class car',3,'26,00','EUR'),
                 ('Karon Beach, Phuket','Standard minivan 8 pax',8,'32,00','EUR')]
                if key=='phuket' else [('Santa Monica','Standard minivan 6 pax',6,'68,00','USD'),
                                        ('Los Angeles Downtown','Standard minivan 6 pax',6,'70,00','USD')])
    for identity in ids:
        item=load_pricebook_attestation(cursor,identity)
        rows=list((item.get('rows') or {}).values())
        if item and all(any(len(r)==7 and str(r[2]).casefold()==dest.casefold()
                           and str(r[3]).casefold()==vehicle.casefold() and int(r[4])==pax
                           and str(r[5]).replace('.',',')==price and r[6]==currency
                           and ('HKT' in str(r[1]) if key=='phuket' else 'LAX' in str(r[1])) for r in rows)
                       for dest,vehicle,pax,price,currency in expected):
            return {'id':identity,'verified_at':item['verified_at'],'source_version':item['source_version']}
    raise ValueError('current_template_prices_required')


MESSAGES={
 'stale_template_preview':'Данные или версия шаблона изменились. Покажите письмо снова перед сохранением.',
 'template_unknown':'Выберите шаблон из списка.', 'template_task_required':'Выберите группу или укажите ID задачи.',
 'template_task_not_found':'Эта группа недоступна в выбранном бизнесе.',
 'template_one_company_required':'Укажите группу с одной компанией. Массовая подготовка этим действием не запускается.',
 'template_qualification_required':'Сначала нужны подтверждённые обязательные требования и публичный контакт. Новая проверка не запускалась.',
 'template_business_mismatch':'Этот шаблон относится к другому отправителю или бизнесу.',
 'template_destination_mismatch':'Направление шаблона не подтверждено в требованиях и источниках этой компании.',
 'company_name_required':'В карточке вместо названия компании указан заголовок страницы. Подтвердите название по официальному источнику.',
 'current_template_prices_required':'Не найдена свежая подтверждённая цена для всех маршрутов шаблона. Старые цены не подставлены; платных запросов нет.',
 'template_sender_required':'Не найден подключённый отправитель этого шаблона.',
 'template_contact_required':'У компании нет подходящего публичного email с источником.',
 'template_task_running':'Сначала приостановите выполняемую задачу. Подготовка по шаблону не меняет её на ходу.',
 'template_suppressed':'Контакт исключён из аутрича или уже ответил. Новое письмо не подготовлено.',
 'english_template_slots_required':'Для английского шаблона нужны сохранённый факт и описание аудитории на английском. Автоматический перевод не запускался.',
}


def execute(cursor,*,business_id,user_id,arguments,actor_context=None):
    from services.outreach_continuation import actor_can_write, effective_qualification, qualified_contact_ids
    base={'charged_credits':0,'external_dispatch_performed':False,'model_called':False,'search_started':False}
    if not actor_can_write(cursor,business_id,actor_context or {}):
        return {**base,'status':'blocked','chat_response':'Нет доступа к этому бизнесу.','blocked_reasons':['access_denied']}
    operation=arguments.get('operation','preview')
    if operation=='list':
        keys=['phuket','la'] if business_id==RIDERRA else ['localos']
        return {**base,'status':'completed','templates':[{'key':k,'label':definition(k)['label']} for k in keys],
            'chat_response':'Шаблоны писем · сборка без генерации и списаний\n\n'+'\n'.join(f"• {definition(k)['label']} ({k})" for k in keys)+
            '\n\nНапишите: «Покажи письмо по шаблону Пхукет для задачи ID». После просмотра: «Сохрани письмо по шаблону Пхукет для задачи ID». Отправка согласуется отдельно.'}
    if arguments.get('workstream_id'):
        return platform_draft(cursor,business_id=business_id,user_id=user_id,arguments=arguments,actor_context=actor_context or {},base=base)
    mutation_started=False
    try:
        if operation not in {'preview','save'}: raise ValueError('template_unknown')
        key=arguments.get('template'); definition(key)
        task_id=arguments.get('task_id')
        if not task_id: raise ValueError('template_task_required')
        cursor.execute("SELECT * FROM operator_async_jobs WHERE id::text=%s AND business_id=%s AND kind='outreach_continue' FOR UPDATE",(task_id,business_id))
        row=cursor.fetchone()
        if not row: raise ValueError('template_task_not_found')
        row=dict(row);state=dict(row.get('result_json') or {});config=row.get('payload_json') or {}
        if row['status'] in {'running','queued','cancelled'}: raise ValueError('template_task_running')
        from services import outreach_campaign_service as c
        cursor.execute("""SELECT w.id,w.lead_id FROM lead_workstreams w WHERE w.client_business_id=%s
            AND w.lead_id::text=ANY(%s::text[]) AND w.workstream_type='client_partnership'""",(business_id,state.get('lead_ids') or []))
        workstreams=[dict(x) for x in cursor.fetchall() if str(x['id']) in state.get('qualifications',{})]
        if len(workstreams)!=1: raise ValueError('template_one_company_required')
        ws=workstreams[0];wid=str(ws['id']);qualification=effective_qualification(state['qualifications'][wid])
        if qualification.get('status')!='qualified' or wid not in qualified_contact_ids(state): raise ValueError('template_qualification_required')
        mode='partner_business' if key!='localos' else 'localos'
        context=c._apply_sender_mode(c._load_context(cursor,wid),mode)
        if str(context.get('client_business_id') or '')!=business_id: raise ValueError('template_business_mismatch')
        if key!='localos' and business_id!=RIDERRA: raise ValueError('template_business_mismatch')
        if key=='localos' and (context.get('workstream_type')!='localos_sales' or not (actor_context or {}).get('is_superadmin')):
            raise ValueError('template_business_mismatch')
        ledger=c.build_evidence_ledger(context)
        # Preserve actual qualified facts, including their official sources.
        for criterion in (qualification.get('criteria') or {}).values():
            if criterion.get('status')=='verified' and isinstance(criterion.get('evidence'),dict):
                evidence=criterion['evidence']; ledger.insert(0,{**evidence,'fact':criterion.get('quote') or evidence.get('fact'),'kind':'public_signal'})
        destination=DEFINITIONS[key][2]
        if destination and (destination.casefold() not in json.dumps(config,ensure_ascii=False).casefold()
                            or not any(destination.casefold() in str(e.get('fact') or '').casefold() and e.get('source_url') for e in ledger)):
            raise ValueError('template_destination_mismatch')
        if context.get('lifecycle_state') in {'replied','refused','unsubscribed','closed_lost'}: raise ValueError('template_suppressed')
        if c._suppression_status(cursor,context).get('suppressed'): raise ValueError('template_suppressed')
        availability=c.channel_availability(cursor,context);email=availability.get('email') or {}
        if not email.get('recipient') or not email.get('contact_point_id'): raise ValueError('template_contact_required')
        sender=next((x for x in email.get('sender_accounts') or [] if str(x.get('sender_identity') or '').lower()==DEFINITIONS[key][3] and x.get('status')=='ready'),None)
        if not sender: raise ValueError('template_sender_required')
        price=prices_current(cursor,key)
        output=render(key,company=context.get('lead_name'),evidence=ledger,audience=config.get('audience') or '',variant=arguments.get('variant','A'))
        revision=hashlib.sha256(json.dumps([output,qualification,email.get('recipient'),sender['id']],sort_keys=True,default=str).encode()).hexdigest()
        response={**base,'status':'completed','search_task_id':task_id,'template_revision':revision,'template':key,'template_variant':output['variant'],
            'chat_response':f"{DEFINITIONS[key][1]} · черновик\n\nКому: {email['recipient']}\nОт: {DEFINITIONS[key][3]}\n\nТема: {output['subject']}\n\n{output['body']}\n\nСборка по шаблону: 0 кредитов. Не отправлено. Текст и цены требуют просмотра перед отправкой.",
            'result_ref':{'href':f'/dashboard/partnerships?business_id={business_id}&search_task_id={task_id}&section=drafts','label':'Открыть письма'},
            'draft':{'subject':output['subject'],'body':output['body'],'recipient':email['recipient'],'sender':DEFINITIONS[key][3]}}
        if operation=='preview':
            response['result_ref']={'href':f'/dashboard/operator?business_id={business_id}&search_task_id={task_id}', 'label':'Открыть чат в мини-приложении'}
            response['chat_response'] += '\nПредварительный просмотр: ещё не сохранено. Для сохранения напишите «Сохрани письмо по шаблону '+DEFINITIONS[key][1].split(' · ')[-1]+' для задачи '+task_id+'».'
            return response
        receipts=dict(state.get('template_draft_receipts') or {})
        save_key=hashlib.sha256(json.dumps([wid,output['subject'],output['body'],output['template']['sha256'],email['recipient'],sender['id']],sort_keys=True).encode()).hexdigest()
        if save_key in receipts:
            current_draft=(state.get('campaign_results') or {}).get(wid,{}).get('draft_id')
            if current_draft: response['result_ref']['href'] += '&draft_id='+str(current_draft)
            return {**response,'campaign_id':receipts[save_key],'already_saved':True,'chat_response':'Этот черновик уже сохранён.\n\n'+response['chat_response']}
        if not arguments.get('revision'):
            return {**response,'saved':False,'chat_response':'Сначала посмотрите этот текст, затем повторите команду сохранения.\n\n'+response['chat_response']}
        if arguments['revision']!=revision: raise ValueError('stale_template_preview')
        cursor.execute('SAVEPOINT template_draft_write')
        mutation_started=True
        gate={'passed':False,'verdict':'revise','score':None,'reason_codes':['template_manual_review_required'],'blocking_reasons':['template_manual_review_required']}
        fact=next(e for e in ledger if e.get('source_url') and e.get('fact'))
        fingerprint=c._context_source_fact_fingerprint(context)
        touch={'sequence_index':0,'channel':'email','day_offset':0,'scheduled_at':datetime.now(timezone.utc),'angle':'business_reputation',
            'subject':output['subject'],'text':output['body'],'quality_gate':gate,'channel_status':'ready',
            'contact_point_id':email['contact_point_id'],'recipient':email['recipient'],'sender_account_id':sender['id'],
            'evidence_id':'template-qualified-fact','evidence_kind':'public_signal','source_url':fact['source_url'],'observation':fact['fact'],
            'source_fact_fingerprint':fingerprint,'generation_source':'saved_template','template_key':output['template']['template_id'],
            'template_version':output['template']['version'],'template_selection':{'key':key,'label':DEFINITIONS[key][1],'definition_sha256':output['template']['sha256'],'slots':output['slots'],'price_snapshot':price},
            'strategy':{'template_key':key,'draft_only':True},'strategy_fingerprint':revision}
        preview={'status':'needs_revision','workstream_id':wid,'workstream_type':context['workstream_type'],'lead_id':str(ws['lead_id']),
            'scope_type':'business','business_id':business_id,'sender_mode':mode,'sender_profile_id':str((context.get('sender_profile') or {})['id']),
            'evidence':ledger,'personalization_candidates':[{'id':'template-qualified-fact'}],'decision':{'action':'review_draft'},
            'touches':[touch],'quality_gate':gate,'generation':{'source':'saved_template','status':'ready'}}
        cursor.execute("""SELECT c.id,c.version FROM outreach_campaigns c JOIN outreach_campaign_touches t ON t.campaign_id=c.id
            WHERE c.workstream_id=%s AND c.business_id=%s AND c.status='draft' AND t.sequence_index=0
              AND t.subject=%s AND t.generated_text=%s
              AND t.message_brief_json->'template_selection'->>'definition_sha256'=%s
              AND t.message_brief_json->>'source_fact_fingerprint'=%s LIMIT 1""",
            (wid,business_id,output['subject'],output['body'],output['template']['sha256'],fingerprint))
        campaign=cursor.fetchone()
        campaign=dict(campaign) if campaign else c.persist_preview(cursor,preview,user_id=user_id)
        cursor.execute("UPDATE outreach_campaigns SET policy_json=policy_json || %s::jsonb WHERE id=%s AND business_id=%s",
                       (Json({'outreach_task_id':task_id}),campaign['id'],business_id))
        from services.partner_search_drafts import project_campaign_draft
        projection=project_campaign_draft(cursor,task_id=task_id,campaign_id=str(campaign['id']),business_id=business_id,user_id=user_id)
        previous=(state.get('campaign_results') or {}).get(wid)
        if previous: state.setdefault('draft_retry_history',[]).append({'workstream_id':wid,'result':previous,'at':datetime.now(timezone.utc).isoformat(),'reason':'saved_template_selected'})
        state.setdefault('campaign_results',{})[wid]={'status':'needs_revision','campaign_id':str(campaign['id']),'lead_id':str(ws['lead_id']),'draft_id':projection['draft_id'],'quality_passed':False,'template_key':key}
        receipts[save_key]=str(campaign['id']);state['template_draft_receipts']=receipts;state['blocker']='draft_quality_review_required'
        # Owner actions hold the row lock, but do not possess a worker lease.
        # Never use the worker-only fenced _save() for an already stopped task.
        stage='Письмо собрано по шаблону; проверьте текст перед отправкой'
        cursor.execute("""UPDATE operator_async_jobs SET result_json=%s,status='waiting_for_review',
            stage=%s,updated_at=NOW() WHERE id=%s AND business_id=%s
            AND status NOT IN ('running','queued','cancelled') RETURNING id""",
            (Json(state),stage,task_id,business_id))
        if not cursor.fetchone(): raise ValueError('template_task_running')
        from services.outreach_chat_results import record
        record(cursor,row,state,'waiting_for_review',stage)
        response['result_ref']['href'] += '&draft_id='+projection['draft_id']
        return {**response,'campaign_id':str(campaign['id']),'saved':True,'chat_response':'Сохранено в «Письмах».\n\n'+response['chat_response']}
    except ValueError as exc:
        if mutation_started: cursor.execute('ROLLBACK TO SAVEPOINT template_draft_write')
        reason=str(exc).strip("'")
        return {**base,'status':'clarification_required','blocked_reasons':[reason],
                'chat_response':MESSAGES.get(reason,'Для этого шаблона не хватает подтверждённых данных. Ничего не запущено и не списано.')}


def platform_draft(cursor,*,business_id,user_id,arguments,actor_context,base):
    """Reuse platform CRM research for the LocalOS partner template; admin only."""
    if arguments.get('template')!='localos' or actor_context.get('session_kind')=='demo' or actor_context.get('impersonating'):
        return {**base,'status':'blocked','chat_response':MESSAGES['template_business_mismatch']}
    cursor.execute('SELECT is_superadmin,is_active FROM users WHERE id=%s',(user_id,))
    actor=cursor.fetchone() or {}
    if not actor.get('is_superadmin') or not actor.get('is_active'):
        return {**base,'status':'blocked','blocked_reasons':['platform_admin_required'],'chat_response':'Шаблон LocalOS доступен администратору платформы.'}
    wid=str(arguments['workstream_id'])
    cursor.execute("SELECT id,lead_id FROM lead_workstreams WHERE id::text=%s AND workstream_type='localos_sales' AND client_business_id IS NULL FOR UPDATE",(wid,))
    ws=cursor.fetchone()
    if not ws:return {**base,'status':'blocked','chat_response':'Карточка LocalOS не найдена.'}
    from services import outreach_campaign_service as c
    context=c._apply_sender_mode(c._load_context(cursor,wid),'localos')
    cursor.execute('SELECT 1 FROM outreach_inbound_events WHERE lead_id=%s AND is_human=TRUE LIMIT 1',(ws['lead_id'],))
    if cursor.fetchone() or c._suppression_status(cursor,context).get('suppressed'):
        return {**base,'status':'blocked','chat_response':MESSAGES['template_suppressed']}
    ledger=c.build_evidence_ledger(context)
    # The approved audience slot is conditional on actual SME/merchant evidence.
    facts=[e for e in ledger if e.get('source_url') and e.get('fact') and re.search(r'\bSMEs?\b|small.business|merchants?|business banking',str(e['fact']),re.I)]
    if not facts:return {**base,'status':'clarification_required','chat_response':'В сохранённых источниках пока не подтверждена работа компании с малым бизнесом. Исследование не запускалось.'}
    email=(c.channel_availability(cursor,context).get('email') or {})
    sender=next((x for x in email.get('sender_accounts') or [] if str(x.get('sender_identity') or '').lower()=='localosgo@gmail.com' and x.get('status')=='ready'),None)
    if not sender or not email.get('contact_point_id'):
        return {**base,'status':'clarification_required','chat_response':'Нужны публичный email с источником и подключённый отправитель localosgo. Ничего не списано.'}
    try: output=render('localos',company=context.get('lead_name'),evidence=facts,audience='your small-business clients with physical locations, such as shops, cafés and salons.')
    except ValueError as exc:return {**base,'status':'clarification_required','chat_response':MESSAGES.get(str(exc),'Проверьте данные компании.')}
    fingerprint=c._context_source_fact_fingerprint(context)
    revision=hashlib.sha256(json.dumps([output,email['recipient'],sender['id'],fingerprint],sort_keys=True).encode()).hexdigest()
    response={**base,'status':'completed','template':'localos','workstream_id':wid,'template_revision':revision,
        'result_ref':{'href':f'/dashboard/operator?business_id={business_id}','label':'Открыть этот чат в мини-приложении'},
        'chat_response':f"LocalOS · партнёрство · черновик\n\nКому: {email['recipient']}\nОт: localosgo@gmail.com\n\nТема: {output['subject']}\n\n{output['body']}\n\nИсточник: {facts[0]['source_url']}\n\nСборка: 0 кредитов. Нужен просмотр; ничего не отправлено.",
        'draft':{'subject':output['subject'],'body':output['body'],'recipient':email['recipient'],'sender':'localosgo@gmail.com'}}
    if arguments.get('operation')!='save':return response
    if arguments.get('revision')!=revision:
        return {**response,'saved':False,'chat_response':'Посмотрите этот текст перед сохранением.\n\n'+response['chat_response']}
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('saved-template:'+wid,))
    cursor.execute("SELECT c.id FROM outreach_campaigns c JOIN outreach_campaign_touches t ON t.campaign_id=c.id WHERE c.workstream_id=%s AND c.scope_type='platform' AND c.status='draft' AND t.strategy_fingerprint=%s LIMIT 1",(wid,revision))
    existing=cursor.fetchone()
    if existing:return {**response,'campaign_id':str(existing['id']),'already_saved':True}
    gate={'passed':False,'verdict':'revise','score':None,'reason_codes':['template_manual_review_required'],'blocking_reasons':['template_manual_review_required']}
    touch={'sequence_index':0,'channel':'email','day_offset':0,'scheduled_at':datetime.now(timezone.utc),'angle':'business_reputation',
        'subject':output['subject'],'text':output['body'],'quality_gate':gate,'channel_status':'ready',
        'contact_point_id':email['contact_point_id'],'recipient':email['recipient'],'sender_account_id':sender['id'],
        'evidence_id':'saved-template-fact','evidence_kind':'public_signal','source_url':facts[0]['source_url'],'observation':facts[0]['fact'],
        'source_fact_fingerprint':fingerprint,'generation_source':'saved_template','template_key':output['template']['template_id'],
        'template_version':output['template']['version'],'template_selection':{'key':'localos','label':DEFINITIONS['localos'][1],'definition_sha256':output['template']['sha256'],'slots':output['slots']},
        'strategy':{'template_key':'localos','draft_only':True},'strategy_fingerprint':revision}
    preview={'status':'needs_revision','workstream_id':wid,'workstream_type':'localos_sales','lead_id':str(ws['lead_id']),
        'scope_type':'platform','business_id':None,'sender_mode':'localos','sender_profile_id':str((context.get('sender_profile') or {})['id']),
        'evidence':ledger,'personalization_candidates':[{'id':'saved-template-fact'}],'decision':{'action':'review_draft'},
        'touches':[touch],'quality_gate':gate,'generation':{'source':'saved_template','status':'ready'}}
    campaign=c.persist_preview(cursor,preview,user_id=user_id)
    return {**response,'saved':True,'campaign_id':str(campaign['id']),'chat_response':'Черновик сохранён в карточке компании.\n\n'+response['chat_response']}
