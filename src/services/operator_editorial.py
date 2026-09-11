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
    return bool(re.search(r'\bтон(?:а|е|ом|у)?\b|тональност',text)) or any(word in text for word in ('акцент', 'фокус', 'индивидуальност', 'запомни', 'факт о', 'факты о', 'моя история')) or (
        any(word in text for word in ('пост', 'контент', 'публикац', 'тему')) and any(word in text for word in ('измен', 'помен', 'замен', 'переработ', 'перепиш', 'расскажу')))


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
    return {'status':'completed','items':[{**{key:row.get(key) for key in ('id','plan_id','theme','goal','scheduled_for','status','plan_status')},'version':_version(row)} for row in rows], 'plans':plans,
            'saved_notes':notes[-30:], 'external_writes_performed':False}


def _change(cursor,row,theme,brief,user_id,focus=None):
    metadata=dict(row.get('metadata_json') or {})
    history=list(metadata.get('operator_edit_history') or [])
    history.append({'theme':row['theme'],'goal':row.get('goal'),'draft_text':row.get('draft_text'),
        'usernews_id':row.get('usernews_id'),'source_before':{key:row.get(key) for key in ('content_type','source_kind','source_ref','seo_keyword','service_id','transaction_id')},'metadata_before':{key:value for key,value in metadata.items() if key!='operator_edit_history'},
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


def editorial_tools(cursor,business_id,user_id,message):
    string=lambda maximum: {'type':'string','maxLength':maximum}
    target={'item_id':string(100),'plan_id':string(100),'version':string(64)}
    tools=[
        {'name':'content.editorial_context','capability':'content.history','title':'Посты и сохранённые сведения для редактирования',
         'description':'Перед правкой прочитай план: id, даты, темы, версии и заметки. Пользователю называй только даты и темы, без технических ID и названий инструментов. Если указан месяц, выбирай только его даты. Если цель неоднозначна, уточни. Возвращает до 200 записей выбранного или последнего плана.',
         'input_schema':{'type':'object','properties':{'plan_id':string(100)}},'risk_class':'read_only',
         'execute':lambda args:read_context(cursor,business_id,user_id,args)},
        {'name':'content.edit_item','capability':'content.item.edit','title':'Изменить тему и бриф поста',
         'description':'Меняет один неопубликованный пост по явной просьбе пользователя. theme и brief — точные цитаты надиктованной новой темы/информации, без слов команды и без выдуманных фактов. Нужна версия из editorial_context. Сохраняет старый текст в истории и помечает необходимость новой генерации. Не создаёт новый план.',
         'input_schema':{'type':'object','required':['item_id','version','theme'],'properties':{**target,'theme':string(500),'brief':string(6000)}},
         'risk_class':'write_internal_draft','execute':lambda args:edit_item(cursor,business_id,user_id,message,args),'deterministic_response':True},
        {'name':'content.refocus_plan','capability':'content.plan.refocus','title':'Изменить акцент контент-плана',
         'description':'Готовит preview новых тем до 20 неопубликованных постов выбранного периода. Сначала editorial_context. focus — точная цитата пожелания. changes — предложенные новые темы, соответствующие пожеланию, без новых фактических утверждений. Если период не указан, уточни его. Все темы будут показаны пользователю до применения. Сохраняет даты и старые тексты. Не создавать новый план вместо правки.',
         'input_schema':{'type':'object','required':['plan_id','focus','changes','period_start','period_end'],'properties':{'plan_id':string(100),'focus':string(1500),'period_start':string(10),'period_end':string(10),
            'changes':{'type':'array','minItems':1,'maxItems':20,'items':{'type':'object','required':['item_id','version','theme'],'properties':{**target,'theme':string(120)}}}}},
         'risk_class':'bulk_write','approval_required':True,'prepare_approval':lambda args:prepare_focus(cursor,business_id,user_id,message,args),'deterministic_preparation_response':True},
        {'name':'content.remember','capability':'content.memory.add','title':'Запомнить факты, историю или пожелание к тону',
         'description':'Сохраняет только реальные сведения о выбранном бизнесе со слов пользователя, его историю или пожелание к тону для будущих текстов. Не сохраняй примеры, гипотезы, вопросы и отрицания. quote — точная полная цитата из текущего сообщения. Не сокращай историю и не добавляй факты. kind company_fact/founder_story/tone. Не использовать для акцента одного месяца — это refocus_plan.',
         'input_schema':{'type':'object','required':['kind','quote'],'properties':{'kind':{'type':'string','enum':['company_fact','founder_story','tone']},'quote':string(6000)}},
         'risk_class':'write_internal_draft','execute':lambda args:remember(cursor,business_id,user_id,message,args),'deterministic_response':True}]
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
    try:
        return handler(arguments)
    except PermissionError:
        return _result('Нет доступа к изменению контента этого бизнеса.', 'denied')
    except ValueError:
        return _result(str(sys.exception()), 'denied')
