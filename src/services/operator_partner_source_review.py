"""Free deterministic review of imported partner copy in any Operator channel."""
import re


def request_for(message):
    text = re.sub(r'\s+', ' ', str(message or '')).strip().rstrip('.!')
    if text.casefold() in {'покажи импорт партнёров','покажи импорт партнеров'}:
        return {'operation':'list'}
    match = re.fullmatch(r'покажи (?:исходное )?сообщение партн[её]ру\s+(.+)', text, re.I)
    return {'operation':'message','company':match[1].strip('«»"')} if match else None


def execute(cursor, *, business_id, user_id, arguments, actor_context):
    from core.auth_helpers import verify_business_write_access
    base = {'charged_credits':0,'model_called':False,'search_started':False,'external_dispatch_performed':False}
    if not verify_business_write_access(cursor,business_id,actor_context or {'user_id':user_id})[0]:
        return {**base,'status':'blocked','chat_response':'Нет доступа к партнёрам выбранного бизнеса.'}
    cursor.execute('''SELECT id,name,pipeline_status,search_payload_json FROM prospectingleads
        WHERE business_id=%s AND intent='partnership_outreach'
        AND jsonb_exists(search_payload_json, 'owner_source_imports') ORDER BY name''',(business_id,))
    rows=[dict(r) for r in cursor.fetchall()]
    href=f'/dashboard/partnerships?business_id={business_id}&section=drafts'
    if arguments.get('operation')=='list':
        histories=sum(any(c.get('history') for c in (r['search_payload_json'].get('owner_source_imports') or {}).values()) for r in rows)
        cursor.execute('''SELECT COUNT(DISTINCT d.lead_id) AS count FROM outreachmessagedrafts d JOIN prospectingleads l ON l.id=d.lead_id
            WHERE l.business_id=%s AND d.learning_note_json->>'source_original'='true' ''',(business_id,))
        drafts=int(cursor.fetchone()['count'])
        text=(f'Компаний в импорте: {len(rows)}.\n'
              f'Прошлый контакт указан в источнике: {histories}. Исходных черновиков: {drafts}.\n'
              'Новых отправок не было. Контакты из таблицы требуют проверки перед отправкой.\n\n'
              'Например: «Покажи сообщение партнёру Lasur».')
        researched = [r for r in rows if r['search_payload_json'].get('owner_contact_research')]
        if researched:
            ready = [r['name'] for r in researched if r['search_payload_json']['owner_contact_research']['state']=='review_ready']
            waiting = [r['name'] for r in researched if r['search_payload_json']['owner_contact_research']['state']!='review_ready']
            text += f'\n\nДополнительно проверено: {len(researched)}. Готовы к просмотру: {len(ready)}. Нужен контакт или уточнение: {len(waiting)}.\n'
            text += 'Готовы: '+', '.join(ready)+'.\nНужно уточнить: '+', '.join(waiting)+'.'
        return {**base,'status':'completed','chat_response':text,'result_ref':{'href':href,'label':'Открыть письма'}}
    name=str(arguments.get('company') or '').casefold()
    selected=[r for r in rows if r['name'].casefold()==name or str(r['id'])==name]
    if len(selected)!=1:
        return {**base,'status':'clarification_required','chat_response':'Укажите точное название партнёра из импортированного списка. Например: «Покажи сообщение партнёру Lasur».'}
    row=selected[0]
    contexts=list((row['search_payload_json'].get('owner_source_imports') or {}).values())
    cursor.execute('''SELECT id,channel,status,generated_text,edited_text,learning_note_json FROM outreachmessagedrafts
        WHERE lead_id=%s AND learning_note_json->>'source_original'='true'
        ORDER BY updated_at DESC,created_at DESC,id DESC LIMIT 1''',(str(row['id']),))
    draft=cursor.fetchone()
    origin = (draft or {}).get('learning_note_json') or {}
    context = next((c for c in contexts if c['source_url'] == origin.get('source_url')), contexts[0])
    history = next((c.get('history') for c in contexts if c.get('history')), None)
    contact=next((c for c in context.get('contacts',[]) if c['type'] in {'email','vk','telegram','max'}),None)
    research = row['search_payload_json'].get('owner_contact_research') or {}
    if research:
        contact = research.get('selected')
    lines=[row['name']]
    if history:
        lines+=['Ранее связались — по исходной таблице.',history.get('comment') or 'Дата не указана.','Новое первое сообщение не подготовлено.']
    else:
        lines+=['Исходный черновик · требует проверки',
                f"Канал: {contact['type']}. Контакт: {contact['value']}" if contact else 'Контакт пока не найден.']
    if draft:
        origin = draft.get('learning_note_json') or {}
        if origin.get('manual_delivery_only') and draft['channel'] == 'vk':
            lines += ['VK: черновик только для ручной отправки.']
        inspection = origin.get('recipient_check') or {}
        if inspection and inspection.get('recipient_eligible') is not True:
            lines += ['Эта Telegram-ссылка не подтверждена как адресат личного сообщения. Нужен другой контакт; текст сохранён.']
        elif inspection.get('entity_type') == 'user':
            lines += ['Подтверждён тип: личный аккаунт. Принадлежность компании и доставка отдельно не подтверждены.']
    if research:
        lines += [{'review_ready':'Контакт найден · текст готов к просмотру',
                   'identity_review':'Нужно уточнить принадлежность контакта',
                   'contact_required':'Нужен контакт для переписки',
                   'possibly_closed':'По источнику филиал закрыт · требуется решение'}.get(research.get('state'),'Требует проверки'), research.get('note') or '']
        lines += ['Контакт: '+c['type']+' · '+c['value'] for c in research.get('contacts',[]) if c['type'] not in {'website'} and c != contact]
        lines += ['Источник контакта: '+source for source in research.get('sources',[])]
    text = ((draft or {}).get('edited_text') or (draft or {}).get('generated_text') or context.get('message'))
    lines+=['',text or 'Исходный текст отсутствует.','',
            'Источник: '+context['source_url'],'Ничего не отправлено.']
    if draft:
        href+='&draft_id='+str(draft['id'])
    return {**base,'status':'completed','chat_response':'\n'.join(lines),
            'result_ref':{'href':href,'label':'Открыть письмо' if draft else 'Открыть партнёров'}}
