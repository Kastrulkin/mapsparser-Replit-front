"""Narrow editorial tools. The planner proposes; this module checks and persists."""
import hashlib
import json
import re
import sys
import uuid
from datetime import date, datetime, timezone
from services.operator_conversations import _row
from services.operator_audio import authorize_actor


EDITABLE = {'planned', 'draft_generated', 'edited'}


def editorial_input(message):
    text = str(message).lower()
    return bool(re.search(r'больше не (?:пиш|обещ|заяв)|правил.{0,20}(?:контент|пост)|не (?:пиши|обещай|заявляй)',text)) or bool(re.search(r'\bтон(?:а|е|ом|у)?\b|тональност',text)) or any(word in text for word in ('акцент', 'фокус', 'индивидуальност', 'запомни', 'факт о', 'факты о', 'моя история')) or (
        any(word in text for word in ('пост', 'контент', 'публикац', 'тему')) and any(word in text for word in ('измен', 'помен', 'замен', 'переработ', 'перепиш', 'переведи', 'перевод', 'расскажу', 'придум', 'напиши')))


def _result(text, status='completed', **extra):
    return {'status': status, 'chat_response': text, 'external_writes_performed': False,
            'result_ref': {'href': '/dashboard/content', 'label': 'Открыть контент', 'entity_type': 'content'}, **extra}


def _quote(value, message, maximum=6000):
    text = str(value or '').strip()
    normalize = lambda value: ' '.join(str(value).casefold().replace('ё','е').split())
    if not text or len(text)>maximum or normalize(text) not in normalize(message):
        raise ValueError('Нужна точная цитата из сообщения пользователя, без добавленных фактов.')
    return text


def _version(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _items(cursor, business_id, plan_id=None, lock=False, item_id=None):
    cursor.execute('''SELECT i.id,i.plan_id,i.business_id,i.theme,i.goal,i.scheduled_for,i.status,i.draft_text,
        i.usernews_id,i.metadata_json,i.updated_at,i.content_type,i.source_kind,i.source_ref,i.seo_keyword,i.service_id,i.transaction_id,p.plan_status FROM contentplanitems i
        JOIN contentplans p ON p.id=i.plan_id
        WHERE i.business_id=%s AND p.business_id=%s
        AND i.plan_id=COALESCE(%s,(SELECT id FROM contentplans WHERE business_id=%s ORDER BY created_at DESC,id DESC LIMIT 1))
        AND i.id=COALESCE(%s,i.id)
        ORDER BY i.scheduled_for,i.id LIMIT 200''' + (' FOR UPDATE OF i' if lock else ''),
        (business_id,business_id,plan_id,business_id,item_id))
    return [_row(cursor,row) for row in cursor.fetchall()]


def read_context(cursor, business_id, user_id, arguments):
    authorize_actor(cursor,user_id,business_id)
    rows=_items(cursor,business_id,arguments.get('plan_id'))
    cursor.execute('SELECT id,title,period_start,period_end FROM contentplans WHERE business_id=%s ORDER BY created_at DESC LIMIT 10',(business_id,))
    plans=[_row(cursor,row) for row in cursor.fetchall()]
    cursor.execute('SELECT preferences_json FROM content_voice_profiles WHERE business_id=%s',(business_id,))
    profile=_row(cursor,cursor.fetchone())
    notes=(profile.get('preferences_json') or {}).get('editorial_notes') or []
    return {'status':'completed','items':[{**{key:row.get(key) for key in (('id','plan_id','theme','goal','scheduled_for','status','plan_status') if arguments.get('include_details') else ('id','plan_id','theme','scheduled_for','status','plan_status'))},'version':_version(row)} for row in rows], 'plans':plans,
            'saved_notes':notes[-5:], 'external_writes_performed':False}


def _change(cursor,row,theme,brief,user_id,focus=None):
    metadata=dict(row.get('metadata_json') or {})
    history=list(metadata.get('operator_edit_history') or [])
    history.append({'theme':row['theme'],'goal':row.get('goal'),'draft_text':row.get('draft_text'),
        'scheduled_for':str(row.get('scheduled_for')),'status':row.get('status'),'usernews_id':row.get('usernews_id'),'source_before':{key:row.get(key) for key in ('content_type','source_kind','source_ref','seo_keyword','service_id','transaction_id')},'metadata_before':{key:value for key,value in metadata.items() if key!='operator_edit_history'},
        'actor':user_id,'at':datetime.now(timezone.utc).isoformat()})
    # Existing generated variants must not look current after a topic change.
    metadata={key:value for key,value in metadata.items() if key not in {'content_generation_v2','content_brief_v1','brief_answers','operator_edit_history','publication_objective'}}
    metadata.update({'operator_edit_history':history, 'brief_answers':{'infopovod':brief,'main_idea':theme},
        'generation_source':'needs_context','generation_error_reason':'topic_changed'})
    if focus: metadata['editorial_focus']=focus
    cursor.execute('''UPDATE contentplanitems SET theme=%s,goal=%s,source_kind='owner',source_ref=%s,content_type='news',seo_keyword=NULL,service_id=NULL,transaction_id=NULL,draft_text=NULL,usernews_id=NULL,status='planned',
        metadata_json=%s::jsonb,updated_at=clock_timestamp() WHERE id=%s AND business_id=%s''',
        (theme,brief,brief,json.dumps(metadata,ensure_ascii=False,default=str),row['id'],row['business_id']))


def edit_item(cursor,business_id,user_id,message,arguments):
    if re.search(r'переведи|перевод|придум|перепиш|напиши|замени\s+(?:этот\s+)?пост',message,re.I):
        return rewrite_item(cursor,business_id,user_id,message,arguments)
    authorize_actor(cursor,user_id,business_id)
    if not re.search(r'измени|изменить|поменя|замени|заменить|перепиш|переработ|вместо|пусть|хочу|давай|сделай',message.lower()) or re.match(r'\s*(?:если|как\b|какой|покажи|можно ли)',message.lower()):
        return _result('Сформулируйте правку поста как команду: какой пост и какая новая тема.', 'clarification_required')
    theme=_quote(arguments.get('theme'),message,500)
    brief=_quote(arguments.get('brief') or theme,message)
    rows=_items(cursor,business_id,arguments.get('plan_id'),lock=True,item_id=arguments.get('item_id'))
    matches=[row for row in rows if row['id']==arguments.get('item_id')]
    if len(matches)!=1: return _result('Уточните пост: назовите дату или тему в плане.', 'clarification_required')
    row=matches[0]
    if row['status'] not in EDITABLE or row['plan_status']=='archived':
        return _result('Этот пост уже утверждён, опубликован или недоступен для правки. Выберите неопубликованный черновик.', 'blocked')
    if arguments.get('version')!=_version(row): return _result('Пост изменился. Прочитайте его заново перед правкой.', 'blocked')
    _change(cursor,row,theme,brief,user_id)
    return _result(f"Изменил тему поста на {row['scheduled_for']}: «{theme}». Сохранил надиктованный бриф. Предыдущий текст сохранён в истории; новый текст ещё нужно подготовить.", item_id=row['id'],result_ref={'href':'/dashboard/content?plan_id='+row['plan_id'],'label':'Открыть план'})


def restore_item(cursor,business_id,user_id,message,arguments):
    if not re.search(r'верни|восстанови|отмени.{0,30}(?:правк|измен)',message,re.I):return _result('Для возврата прежнего текста нужна явная команда.', 'clarification_required')
    authorize_actor(cursor,user_id,business_id)
    rows=_items(cursor,business_id,arguments.get('plan_id'),lock=True,item_id=arguments.get('item_id'))
    if len(rows)!=1 or rows[0]['id']!=arguments.get('item_id'):return _result('Выберите пост.', 'clarification_required')
    row=rows[0]
    if row['status'] not in EDITABLE or row['plan_status']=='archived' or arguments.get('version')!=_version(row):return _result('Пост изменился или недоступен для правки.', 'blocked')
    history=(row.get('metadata_json') or {}).get('operator_edit_history') or []
    if not history:return _result('Предыдущей версии нет.', 'blocked')
    previous=history[-1]
    current_metadata=dict(row.get('metadata_json') or {})
    restored_metadata=dict(previous.get('metadata_before') or current_metadata)
    restored_metadata['operator_edit_history']=history+[{
        **{key:row.get(key) for key in ('theme','goal','draft_text','scheduled_for','status','usernews_id')},
        'metadata_before':{key:value for key,value in current_metadata.items() if key!='operator_edit_history'},
        'source_before':{key:row.get(key) for key in ('content_type','source_kind','source_ref','seo_keyword','service_id','transaction_id')},
        'actor':user_id,'at':datetime.now(timezone.utc).isoformat()}]
    source=previous.get('source_before') or row
    cursor.execute("""UPDATE contentplanitems SET theme=%s,goal=%s,draft_text=%s,status=%s,usernews_id=%s,
        scheduled_for=%s,metadata_json=%s::jsonb,content_type=%s,source_kind=%s,source_ref=%s,
        seo_keyword=%s,service_id=%s,transaction_id=%s,updated_at=clock_timestamp() WHERE id=%s AND business_id=%s""",
        (previous['theme'],previous.get('goal'),previous.get('draft_text'),previous['status'],previous.get('usernews_id'),
         previous.get('scheduled_for'),json.dumps(restored_metadata,ensure_ascii=False,default=str),
         source.get('content_type'),source.get('source_kind'),source.get('source_ref'),source.get('seo_keyword'),
         source.get('service_id'),source.get('transaction_id'),row['id'],business_id))
    updated=_items(cursor,business_id,row['plan_id'],item_id=row['id'])[0]
    return _result('Вернул предыдущую версию поста и её дату.',selected_item={'item_id':row['id'],'plan_id':row['plan_id'],'version':_version(updated)})


def preserve_requested_links(text, previous, message):
    if not re.search(r'(?:остав|сохран)\w*[^.!?]{0,60}ссыл|ссыл[^.!?]{0,60}(?:остав|сохран)', message, re.I):
        return text
    links=list(dict.fromkeys(url.rstrip('.,)') for url in re.findall(r'https?://[^\s<>\]\"]+', previous)))
    if len(links)==1:
        text=re.sub(r'\[ссылка[^\]]*\]', lambda _:links[0], text, flags=re.I)
    for link in links:
        if link not in text:
            text+='\n'+link
    return text


def rewrite_item(cursor,business_id,user_id,message,arguments):
    """Generate before mutating the selected draft; preserve its date and history."""
    authorize_actor(cursor,user_id,business_id)
    if re.match(r'\s*(?:не\b|если\b|как\b|можно ли)',message,re.I):
        return _result('Изменения не выполнены.', 'clarification_required')
    rows=_items(cursor,business_id,arguments.get('plan_id'),lock=True,item_id=arguments.get('item_id'))
    matches=[row for row in rows if row['id']==arguments.get('item_id')]
    if len(matches)!=1:return _result('Уточните дату или тему поста.', 'clarification_required')
    row=matches[0]
    if row['status'] not in EDITABLE or row['plan_status']=='archived':return _result('Опубликованный или недоступный пост нельзя переписать.', 'blocked')
    if arguments.get('version')!=_version(row):return _result('Пост изменился. Прочитайте его заново.', 'blocked')
    from services.operator_social_post_generation import _default_social_post_generator, _build_social_post_prompt
    from services.operator_news_generation import _load_business_context
    business=_load_business_context(cursor,business_id)
    prompt=_build_social_post_prompt(source_text=message,business=business)
    prompt+='\nЭто редакционное задание, а не готовый текст. Придумай подачу и формулировки самостоятельно. Не требуй точную формулировку от пользователя. Не выдумывай цены, скидки, гарантии, наличие услуг или ссылки. Если ссылки нет в подтверждённых данных, оставь [ссылка для бронирования].'
    prompt+='\nПредыдущая тема: '+str(row['theme'])+'\nПредыдущий текст (не источник новых фактов): '+str(row.get('draft_text') or '')
    if re.search(r'переведи|перевести|перевод',message,re.I):prompt+='\nПереведи выбранный текст на язык, указанный пользователем. Это указание имеет приоритет над языком шаблона.'
    prompt+='\nЕсли пользователь просит сохранить ссылку, перенеси исходный URL без изменений, включая параметры. Не заменяй известную ссылку заглушкой.'
    prompt+='\n'+editorial_prompt(cursor,business_id)
    translating=bool(re.search(r'переведи|перевести|перевод',message,re.I))
    if translating:
        prompt=prompt.replace('Подготовь пост для соцсетей на русском языке.','Переведи существующий текст на язык, который указал пользователь.')
        prompt+='\nФинальная задача: '+message+'\nВерни JSON с post на запрошенном языке. Не подменяй перевод редактированием русского текста.'
    text=None
    for attempt in range(2):
        try:
            raw=_default_social_post_generator(prompt,business_id=business_id,user_id=user_id)
            raw=re.sub(r'^```(?:json)?\s*|\s*```$','',str(raw).strip())
            generated=json.loads(raw)
            if not isinstance(generated,dict) or not isinstance(generated.get('post'),str):raise ValueError('invalid generation')
            text=preserve_requested_links(generated['post'].strip(), str(row.get('draft_text') or ''), message)
            if len(text.strip())<30:raise ValueError('empty generation')
            if translating and re.search(r'англий',message,re.I) and len(re.findall('[А-Яа-я]',text))>20:raise ValueError('translation language mismatch')
            allowed=set(re.findall(r'https?://[^\s<>\]\"]+',prompt))
            actual=set(re.findall(r'https?://[^\s<>\]\"]+',text))
            if any(url.rstrip('.,)') not in {item.rstrip('.,)') for item in allowed} for url in actual):raise ValueError('unverified link')
            break
        except Exception:
            text=None
    if text is None:
        return _result('Не удалось подготовить новый текст. Пост остался прежним.', 'failed')
    try:
        from services.content_rules import enforce
        text=enforce(cursor,business_id,user_id,text,_default_social_post_generator,message)
        allowed={url.rstrip('.,)') for url in re.findall(r'https?://[^\s<>\]\"]+',prompt)}
        if any(url.rstrip('.,)') not in allowed for url in re.findall(r'https?://[^\s<>\]\"]+',text)):
            raise ValueError('unverified link after repair')
        linked=preserve_requested_links(text, str(row.get('draft_text') or ''), message)
        if linked != text:
            from services.content_rules import validate
            text=validate(cursor,business_id,user_id,linked,_default_social_post_generator,message)

    except Exception:
        return _result('Текст не прошёл проверку правил бизнеса. Пост остался прежним.', 'failed')
    authorize_actor(cursor,user_id,business_id)
    theme=str(arguments.get('theme') or row['theme']).strip()[:500]
    _change(cursor,row,theme,message,user_id)
    cursor.execute("UPDATE contentplanitems SET draft_text=%s,status='draft_generated',metadata_json=(metadata_json-'generation_error_reason')||%s::jsonb,updated_at=clock_timestamp() WHERE id=%s AND business_id=%s",
        (text,json.dumps({'generation_source':'operator_rewrite'}),row['id'],business_id))
    updated=_items(cursor,business_id,row['plan_id'],item_id=row['id'])[0]
    return _result('Переписал пост на '+str(row['scheduled_for'])+'.\n\n'+text+'\n\nПредыдущая версия сохранена в истории.',
        item_id=row['id'],selected_item={'item_id':row['id'],'plan_id':row['plan_id'],'version':_version(updated)},
        result_ref={'href':'/dashboard/content?plan_id='+row['plan_id'],'label':'Открыть пост','entity_type':'content'})


def prepare_focus(cursor,business_id,user_id,message,arguments):
    authorize_actor(cursor,user_id,business_id)
    focus=_quote(arguments.get('focus'),message,1500)
    changes=arguments.get('changes')
    if not isinstance(changes,list) or not 1<=len(changes)<=20:
        return _result('Выберите период с 1–20 постами для изменения акцента.', 'clarification_required')
    try:
        period_start=date.fromisoformat(arguments.get('period_start') or '')
        period_end=date.fromisoformat(arguments.get('period_end') or '')
        if period_end<period_start or (period_end-period_start).days>90: raise ValueError('range')
    except ValueError:
        return _result('Уточните период изменения плана, не больше 90 дней.', 'clarification_required')
    rows=_items(cursor,business_id,arguments.get('plan_id'))
    by_id={row['id']:row for row in rows}
    selected=[];seen=set()
    for change in changes:
        row=by_id.get(change.get('item_id'))
        theme=str(change.get('theme') or '').strip()
        if not row or row['id'] in seen or not 1<=len(theme)<=120:
            return _result('Не удалось однозначно выбрать посты. Уточните план и период.', 'clarification_required')
        if not period_start<=row['scheduled_for']<=period_end:
            return _result('Выбранный пост вне указанного периода. Уточните даты.', 'blocked')
        if row['status'] not in EDITABLE or row['plan_status']=='archived':
            return _result('В выбранном периоде есть защищённый пост. Подготовьте изменения только для неопубликованных черновиков.', 'blocked')
        if change.get('version')!=_version(row): return _result('План изменился. Нужно обновить список постов.', 'blocked')
        selected.append({'id':row['id'],'version':_version(row),'theme':theme,'date':str(row['scheduled_for'])})
        seen.add(row['id'])
    expected={row['id'] for row in rows if row['status'] in EDITABLE and row['plan_status']!='archived' and period_start<=row['scheduled_for']<=period_end}
    if seen!=expected:
        return _result(f'В этом периоде {len(expected)} доступных постов. Нужно включить их все в preview или выбрать более узкий период (до 20 постов).', 'clarification_required')
    plan_id=rows[0]['plan_id']
    cursor.execute('SELECT updated_at FROM contentplans WHERE id=%s AND business_id=%s',(plan_id,business_id))
    plan_version=str(_row(cursor,cursor.fetchone()).get('updated_at'))
    lines=[f"{item['date']}: {item['theme']}" for item in selected]
    return _result('Предлагаю изменить акцент плана. Новые темы:\n\n'+'\n'.join(lines)+'\n\nПодтвердите эти изменения. Предыдущие тексты сохранятся в истории; публикации не выполняются.',
        'approval_required', approval={'envelope':{'business_id':business_id,'plan_id':plan_id,'plan_version':plan_version,'focus':focus,'period_start':str(period_start),'period_end':str(period_end),'changes':selected}})


def apply_focus(cursor,business_id,user_id,envelope):
    if envelope.get('kind')=='revision':
        from services.operator_plan_revision import apply
        return apply(cursor,business_id,user_id,envelope)
    authorize_actor(cursor,user_id,business_id)
    if envelope.get('business_id')!=business_id: return _result('Чужой план.', 'blocked')
    cursor.execute('SELECT updated_at FROM contentplans WHERE id=%s AND business_id=%s FOR UPDATE',(envelope['plan_id'],business_id))
    plan=_row(cursor,cursor.fetchone())
    if not plan or str(plan.get('updated_at'))!=envelope.get('plan_version'): return _result('План изменился после preview. Подготовьте изменения заново.', 'blocked')
    rows={row['id']:row for row in _items(cursor,business_id,envelope['plan_id'],lock=True)}
    changes=envelope['changes']
    if not changes or any(not rows.get(change['id']) or _version(rows[change['id']])!=change['version'] or rows[change['id']]['status'] not in EDITABLE for change in changes):
        return _result('Один из постов изменился после preview. Ничего не применено; подготовьте изменения заново.', 'blocked')
    start=date.fromisoformat(envelope['period_start']);end=date.fromisoformat(envelope['period_end'])
    expected={row['id'] for row in rows.values() if row['status'] in EDITABLE and row['plan_status']!='archived' and start<=row['scheduled_for']<=end}
    if expected!={change['id'] for change in changes}:
        return _result('Состав постов за период изменился. Подготовьте новое preview.', 'blocked')
    for change in changes:
        _change(cursor,rows[change['id']],change['theme'],envelope['focus'],user_id,focus=envelope['focus'])
    cursor.execute("UPDATE contentplans SET generated_plan_json=jsonb_set(COALESCE(generated_plan_json,'{}'::jsonb),'{editorial_focus}',%s::jsonb),updated_at=clock_timestamp() WHERE id=%s AND business_id=%s",
        (json.dumps(envelope['focus'],ensure_ascii=False),envelope['plan_id'],business_id))
    return _result(f"Изменил акцент и темы {len(changes)} постов. Старые тексты сохранены в истории. Новые тексты ещё нужно подготовить.", changed_count=len(changes))


def remember(cursor,business_id,user_id,message,arguments):
    authorize_actor(cursor,user_id,business_id)
    quote=_quote(arguments.get('quote'),message)
    kind=arguments.get('kind')
    if kind not in {'company_fact','founder_story','tone'}: raise ValueError('Неизвестный тип сведений')
    if re.search(r'не (?:пиши|писать|обещай|обещать|заявляй|заявлять)|запрет|ограничени',quote,re.I):
        return _result('Это правило для будущего контента. Используйте изменение правила, чтобы сохранить область действия и историю.', 'clarification_required')
    if re.match(r'\s*(?:если|допустим|например)\b',message.lower()) or re.search(r'не\s+(?:сохраняй|запоминай)',message.lower()):
        return _result('Это пример или факт, который нужно сохранить для вашего бизнеса?', 'clarification_required')
    cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('editorial-profile:'+business_id,))
    cursor.execute('SELECT preferences_json FROM content_voice_profiles WHERE business_id=%s FOR UPDATE',(business_id,))
    profile=_row(cursor,cursor.fetchone());preferences=dict(profile.get('preferences_json') or {})
    notes=list(preferences.get('editorial_notes') or [])
    if any(note.get('kind')==kind and note.get('text')==quote for note in notes): return _result('Эти сведения уже сохранены.')
    if len(notes)>=100: return _result('В профиле уже 100 заметок. Сначала пересмотрите сохранённые сведения.', 'blocked')
    notes.append({'id':str(uuid.uuid4()),'kind':kind,'text':quote,'source':'user_statement','actor_id':user_id,'created_at':datetime.now(timezone.utc).isoformat()})
    preferences['editorial_notes']=notes
    if kind=='tone': preferences['tone_instruction']=quote
    cursor.execute('''INSERT INTO content_voice_profiles(business_id,preferences_json,status,created_by) VALUES (%s,%s::jsonb,'confirmed',%s)
        ON CONFLICT(business_id) DO UPDATE SET preferences_json=EXCLUDED.preferences_json,version=content_voice_profiles.version+1,updated_at=clock_timestamp()''',
        (business_id,json.dumps(preferences,ensure_ascii=False),user_id))
    display=quote if len(quote)<=2500 else quote[:2500]+'…\nПолный текст сохранён: '+str(len(quote))+' символов.'
    return _result('Сохранил для будущих текстов со слов пользователя:\n\n'+display+'\n\nУже подготовленные и опубликованные посты не изменены.', note_id=notes[-1]['id'])


def editorial_prompt(cursor,business_id):
    from services.content_rules import prompt
    return _editorial_profile_prompt(cursor,business_id)+prompt(cursor,business_id)


def _editorial_profile_prompt(cursor,business_id):
    cursor.execute('SELECT preferences_json FROM content_voice_profiles WHERE business_id=%s',(business_id,))
    preferences=(_row(cursor,cursor.fetchone()).get('preferences_json') or {})
    notes=preferences.get('editorial_notes') or []
    selected=[];size=0
    for note in reversed([note for note in notes if note.get('kind')!='tone'][-20:]):
        length=len(json.dumps(note,ensure_ascii=False))
        if size+length>16000: continue
        selected.insert(0,note);size+=length
    return 'Сведения со слов пользователя, не независимо проверенные факты. Используй только уместные сведения, не придумывай достижения, биографию или медицинские обещания. Не повторяй всю историю в каждом посте.\n'+json.dumps(
        {'facts_and_story':selected,'tone':preferences.get('tone_instruction')},ensure_ascii=False) if notes else ''


def editorial_tools(cursor,business_id,user_id,message,channel="web"):
    string=lambda maximum: {'type':'string','maxLength':maximum}
    target={'item_id':string(100),'plan_id':string(100),'version':string(64)}
    from services import operator_plan_revision
    tools=[
        {'name':'content.editorial_context','capability':'content.history','title':'Посты и сохранённые сведения для редактирования',
         'description':'Перед правкой прочитай план: id, даты, темы, версии и заметки. Пользователю называй только даты и темы, без технических ID и названий инструментов. Если указан месяц, выбирай только его даты. Если цель неоднозначна, уточни. Возвращает до 200 записей выбранного или последнего плана.',
         'input_schema':{'type':'object','properties':{'plan_id':string(100),'include_details':{'type':'boolean'}}},'risk_class':'read_only',
         'execute':lambda args:read_context(cursor,business_id,user_id,args)},
        {'name':'content.restore_item','capability':'content.item.edit','title':'Вернуть предыдущий текст поста',
         'description':'Только по явной просьбе отменить последнюю правку или вернуть предыдущий текст выбранного неопубликованного поста. Требуется свежая версия из editorial_context.',
         'input_schema':{'type':'object','required':['item_id','version'],'properties':target},
         'risk_class':'write_internal_draft','execute':lambda args:restore_item(cursor,business_id,user_id,message,args),'deterministic_response':True},
        {'name':'content.rewrite_item','capability':'content.item.edit','title':'Придумать или переписать текст выбранного поста',
         'description':'Используй для замени пост на пост о теме, придумай сам, напиши текст, сделай короче/живее/менее рекламно. Генерирует и сохраняет полноценный текст в той же записи плана, дата сохраняется. Не требует готового текста пользователя. Сначала прочитай editorial_context и выбери точный item_id и версию. theme — редакционный заголовок по заданию, не обязательно цитата. Факты и обещания не выдумываются. Для изменения только темы без текста используй edit_item.',
         'input_schema':{'type':'object','required':['item_id','version','theme'],'properties':{**target,'theme':string(500)}},
         'risk_class':'write_internal_draft','execute':lambda args:rewrite_item(cursor,business_id,user_id,message,args),'deterministic_response':True},
        {'name':'content.edit_item','capability':'content.item.edit','title':'Изменить тему и бриф поста',
         'description':'Меняет один неопубликованный пост по явной просьбе пользователя. Только изменение темы без генерации текста. Если пользователь просит придумать или заменить сам пост, используй rewrite_item. theme и brief — точные цитаты надиктованной новой темы/информации, без слов команды и без выдуманных фактов. Нужна версия из editorial_context. Сохраняет старый текст в истории и помечает необходимость новой генерации. Не создаёт новый план.',
         'input_schema':{'type':'object','required':['item_id','version','theme'],'properties':{**target,'theme':string(500),'brief':string(6000)}},
         'risk_class':'write_internal_draft','execute':lambda args:edit_item(cursor,business_id,user_id,message,args),'deterministic_response':True},
        {'name':'content.rebuild_plan','capability':'content.plan.refocus','title':'Переработать темы и расписание плана',
         'description':'Переработать текущий или выбранный план, изменить число постов, частоту и распределение тем. Одно подтверждение перед применением. Передай post_count и interval_days из команды (один в неделю = 7 дней); план сам вычислит даты. Если число неясно — уточни. Не создавать новый план вместо правки. По умолчанию выбран последний действующий план.',
         'input_schema':{'type':'object','required':['post_count','interval_days'],'properties':{'selector':{'type':'string','enum':['latest','today','current']},'plan_id':string(100),'post_count':{'type':'integer','minimum':1,'maximum':90},'interval_days':{'type':'integer','minimum':1,'maximum':90},'start_date':string(10),'extend_period':{'type':'boolean'}}},
         'risk_class':'bulk_write','approval_required':True,'prepare_approval':lambda args:operator_plan_revision.prepare(cursor,business_id,user_id,message,{**args,"_channel":channel},queue=True),'deterministic_preparation_response':True},
        {'name':'content.refocus_plan','capability':'content.plan.refocus','title':'Изменить акцент контент-плана',
         'description':'Готовит preview новых тем до 20 неопубликованных постов выбранного периода. Сначала editorial_context. focus — точная цитата пожелания. changes — предложенные новые темы, соответствующие пожеланию, без новых фактических утверждений. Если период не указан, уточни его. Все темы будут показаны пользователю до применения. Сохраняет даты и старые тексты. Не создавать новый план вместо правки.',
         'input_schema':{'type':'object','required':['plan_id','focus','changes','period_start','period_end'],'properties':{'plan_id':string(100),'focus':string(1500),'period_start':string(10),'period_end':string(10),
            'changes':{'type':'array','minItems':1,'maxItems':20,'items':{'type':'object','required':['item_id','version','theme'],'properties':{**target,'theme':string(120)}}}}},
         'risk_class':'bulk_write','approval_required':True,'prepare_approval':lambda args:prepare_focus(cursor,business_id,user_id,message,args),'deterministic_preparation_response':True},
        {'name':'content.remember','capability':'content.memory.add','title':'Запомнить факты, историю или пожелание к тону',
         'description':'Сохраняет только реальные сведения о выбранном бизнесе со слов пользователя, его историю или пожелание к тону для будущих текстов. Не сохраняй примеры, гипотезы, вопросы и отрицания. quote — точная полная цитата из текущего сообщения. Не сокращай историю и не добавляй факты. kind company_fact/founder_story/tone. Не использовать для акцента одного месяца — это refocus_plan.',
         'input_schema':{'type':'object','required':['kind','quote'],'properties':{'kind':{'type':'string','enum':['company_fact','founder_story','tone']},'quote':string(6000)}},
         'risk_class':'write_internal_draft','execute':lambda args:remember(cursor,business_id,user_id,message,args),'deterministic_response':True}]
    from services.content_rules import change, load, prepare_network
    def rule_change(args):
        cursor.execute("SELECT id FROM operatormessages WHERE business_id=%s AND user_id=%s AND role='user' ORDER BY created_at DESC,id DESC LIMIT 1",(business_id,user_id))
        rule_request_id=_row(cursor,cursor.fetchone()).get('id') or message
        if re.search(r'(^|[.!?]\s*)(если|допустим|например|может|а что если)\b',message,re.I) or message.rstrip().endswith('?'):
            return _result('Обсуждаем вариант; правила пока не изменены.', 'clarification_required')
        quote=_quote(args.get('text'),message)
        from services.content_rules import can_manage
        if not can_manage(cursor,user_id,business_id):
            from services.work_journal import save_note
            entry=save_note(cursor,business_id,user_id,channel,rule_request_id,
                'content-rule-proposal:'+str(rule_request_id),message,{'quote':quote,'outcome':'note','category':'idea'})
            return _result('Предложение сохранено в рабочем журнале на разбор. Действующие правила не изменены.',
                journal_entries=[entry],result_ref={'href':'/dashboard/work-journal?business_id='+business_id+'&entry='+entry['id'],'label':'Открыть запись'})
        from services.content_rules import spoken_period
        starts_at,ends_at=spoken_period(cursor,business_id,message,args.get('starts_at'),args.get('ends_at'))
        rule=change(cursor,business_id=business_id,user_id=user_id,
            request_id='operator-rule:'+str(uuid.uuid5(uuid.NAMESPACE_URL,business_id+user_id+message+str(args)+str(rule_request_id))),
            text=quote,rule_id=args.get('rule_id'),expected_version=args.get('expected_version'),
            status=args.get('status','active'),starts_at=starts_at,ends_at=ends_at,source=channel)
        return _result('Правило '+('отменено' if rule['status']=='cancelled' else 'сохранено')+': '+rule['text']+
            '\nНастройки: «Профиль и бизнес → Правила для контента». Старые посты не изменены.',
            rule_id=rule['id'],rule_version=rule['version'])
    tools.extend([
        {'name':'content.rules.network','capability':'content.rules.network','title':'Правило для сети',
         'description':'Только по явной просьбе применить правило ко всей сети. Возвращает список точек и отдельное подтверждение массового изменения. text — точная цитата пользователя.',
         'input_schema':{'type':'object','required':['text'],'properties':{'text':string(6000)}},
         'risk_class':'bulk_write','approval_required':True,'deterministic_preparation_response':True,
         'prepare_approval':lambda args:prepare_network(cursor,business_id,user_id,message,_quote(args.get('text'),message))},
        {'name':'content.rules.read','capability':'content.history','title':'Действующие правила контента',
         'description':'Читать правила перед изменением или отменой: используй актуальные id и version.',
         'input_schema':{'type':'object','properties':{}},'risk_class':'read_only',
         'execute':lambda args: {'rules':load(cursor,business_id).get('content_rules',[])}},
        {'name':'content.rules.change','capability':'content.memory.add','title':'Изменить правило контента',
         'description':'Явное постоянное ограничение или временный акцент для выбранного бизнеса. Не для правки одного поста, вопроса или гипотезы. При конфликте сначала уточни замену. Сроки ISO8601 с часовым поясом бизнеса; если пояс неизвестен, уточни. Для изменения/отмены сначала прочитай правила. quote text — полная цитата пользователя. Правила других точек не меняет.',
         'input_schema':{'type':'object','required':['text'],'properties':{'text':string(6000),'rule_id':string(100),
            'expected_version':{'type':'integer'},'status':{'type':'string','enum':['active','cancelled']},'starts_at':string(50),'ends_at':string(50)}},
         'risk_class':'write_internal_draft','execute':rule_change,'deterministic_response':True}])
    import os
    pilots={value.strip() for value in os.getenv('OPERATOR_PLAN_REVISION_ASYNC_BUSINESS_IDS','').split(',') if value.strip()}
    if business_id not in pilots:tools=[tool for tool in tools if tool['name']!='content.rebuild_plan']
    for tool in tools:
        for key in ('execute','prepare_approval'):
            if key in tool:
                handler=tool[key]
                tool[key]=lambda args,handler=handler: _invoke(handler,args)
    return tools


def editorial_evidence(cursor,business_id):
    cursor.execute('SELECT preferences_json FROM content_voice_profiles WHERE business_id=%s',(business_id,))
    notes=((_row(cursor,cursor.fetchone()).get('preferences_json') or {}).get('editorial_notes') or [])
    return [{'id':'owner_note_'+note['id'],'type':'owner','label':'Со слов пользователя','fact':note['text'],
        'story_evidence':note.get('kind')=='founder_story'} for note in notes if note.get('kind') in {'company_fact','founder_story'}][-6:]


def _invoke(handler,arguments):
    from services.operator_plan_continuation import PlanClarification
    from services.content_plan_direction import PlanGenerationError
    try:
        return handler(arguments)
    except PlanGenerationError:
        return _result(str(sys.exception()), 'failed')
    except PlanClarification:
        return _result(str(sys.exception()), 'clarification_required')
    except PermissionError:
        return _result('Нет доступа к изменению контента этого бизнеса.', 'denied')
    except ValueError:
        return _result(str(sys.exception()), 'denied')
