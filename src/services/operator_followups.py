"""Deterministic handling of explicit follow-ups and addressed work notes."""
import re
from datetime import datetime, timezone
from services import operator_editorial, operator_work_journal, work_journal, work_review


def _photo_target(cursor, business_id, history):
    for entry in reversed(history or []):
        value = entry.get('result_json') or {}
        if value.get('selected_item'):
            return value['selected_item']
        if entry.get('role') == 'user':
            match = re.search(r'пост\w*\s+[«"]([^»"]+)[»"]', entry.get('content') or '', re.I)
            if match:
                rows = [row for row in operator_editorial._items(cursor, business_id)
                        if row.get('theme', '').casefold() == match[1].casefold()]
                if len(rows) == 1:
                    row = rows[0]
                    return {'item_id':row['id'], 'plan_id':row['plan_id'], 'version':operator_editorial._version(row)}
                return None
    return None


def remember_selection(cursor, business_id, result, history=None):
    if result.get('photos'):
        selected = _photo_target(cursor, business_id, history)
        if selected:
            result['selected_item'] = selected
        return
    items = result.get('items')
    if result.get('resource') != 'content' or not isinstance(items, list) or len(items) != 1:
        return
    item = items[0]
    if item.get('kind') != 'content_plan_item' or not item.get('plan_id'):
        return
    rows = operator_editorial._items(cursor, business_id, item['plan_id'], item_id=item['id'])
    if len(rows) == 1 and (not item.get('updated_at') or str(item['updated_at']).replace(' ', 'T') == str(rows[0]['updated_at']).replace(' ', 'T')):
        result['selected_item'] = {'item_id': rows[0]['id'], 'plan_id': rows[0]['plan_id'],
                                   'version': operator_editorial._version(rows[0])}


def directed_note(message):
    if re.search(r'\?|\b(?:если|например|допустим|не записывай|не сохраняй)\b', message, re.I):
        return None
    if not re.search(r'передай.{0,30}(?:руководител|администратор)|для (?:руководител|администратор)|пожелание клиента|есть идея', message, re.I):
        return None
    if re.search(r'создай задачу|назначь|измени|опубликуй|отправь клиент|верни деньги', message, re.I):
        return None
    category = ('complaint' if re.search(r'недоволь|жалоб|пожалов|плохо встрет', message, re.I) else
                'wish' if re.search(r'пожелани|хотелось бы|клиент.{0,20}прос|попросил', message, re.I) else
                'idea' if re.search(r'идея|предлагаю', message, re.I) else None)
    if category == 'complaint' and re.search(r'\b(?:возможно|может|будет)\b|была бы|был бы',message,re.I):
        return None
    if re.search(r'клиент\w*.{0,70}отказал',message,re.I):
        return {'quote':message,'category':category or 'other','outcome':'declined'}
    return {'quote': message, 'category': category, 'outcome': 'note'} if category else None


def route(cursor, *, business_id, user_id, channel, message, history, conversation_id, payload, actor, access):
    from services.operator_core import standardize_operator_result, operator_subscription_block
    from services.operator_tool_billing import run_paid_operator_tool_loop
    command=re.sub(r'^\s*(?:пожалуйста[,\s]*|(?:можешь|можете|можно)\s+(?:пожалуйста[,\s]*)?)','',message,flags=re.I)
    if photo_read_request(message):
        blocked = operator_subscription_block(access, 'content.history')
        if blocked:
            return blocked, {}
        result = operator_editorial._read_photo_library(cursor, business_id, user_id, message, max_results=5)
        remember_selection(cursor, business_id, result,
                           [*(history or []), {'role': 'user', 'content': message}])
        return standardize_operator_result(result, 'content.history'), {}
    photo_result = select_shown_photo(cursor, business_id, user_id, message, history)
    if photo_result is not None:
        blocked = operator_subscription_block(access, 'content.item.edit')
        if blocked:
            return blocked, {}
        # The selector resolves context only; the existing editor owns rights,
        # row locking, version checks and publication-approval invalidation.
        args = photo_result.pop('_photo_update', None)
        if args:
            photo_result = operator_editorial.update_item_fields(cursor, business_id, user_id, args)
            if photo_result.get('status') == 'completed':
                photo_result['chat_response'] = 'Сохранил выбранное фото в посте. Публикацию и отправку не запускал.'
        return standardize_operator_result(photo_result, 'content.item.edit'), {}
    from services import operator_voice_followups
    try:
        corrected=operator_voice_followups.route(cursor,business_id=business_id,user_id=user_id,channel=channel,
            message=message,history=history,request_id=str(payload.get('request_id') or conversation_id)+':correction')
    except (ValueError,PermissionError):
        import sys
        corrected={'status':'clarification_required','chat_response':str(sys.exception())}
    if corrected is not None:
        return standardize_operator_result(corrected,corrected.get('capability') or 'content.item.edit'), {}
    if work_journal.enabled(business_id):
        correction=re.match(r'\s*(исправь|измени|отмени|удали)\s+(?:эту\s+)?(?:заметку|запись)\b[:.,\s]*(.*)',command,re.I)
        if correction:
            previous=next((r for r in reversed(history or []) if r.get('role') in {'operator','assistant'}),{})
            entries=(previous.get('result_json') or {}).get('journal_entries') or []
            if len(entries)!=1:
                return standardize_operator_result(operator_work_journal.result('Выберите запись в рабочем журнале или назовите её текст.','clarification_required'),'work.journal'),{}
            selected=entries[0]
            args={'id':selected['id'],'version':selected['version']}
            if correction[1].lower() in {'отмени','удали'}:args['void']=True
            elif correction[2].strip():args['quote']=correction[2].strip()
            else:return standardize_operator_result(operator_work_journal.result('Как должен звучать исправленный текст записи?','clarification_required'),'work.journal'),{}
            try:
                saved=[]
                message_id=next((r.get('id') for r in reversed(history or []) if r.get('role')=='user'),None)
                tools=operator_work_journal.tools(cursor,business_id,user_id,channel,message,message_id,str(payload.get('request_id') or message_id),saved)
                result=next(t for t in tools if t['name']=='work.save_observation')['execute'](args)
                result['journal_entries']=saved
                return standardize_operator_result(result,'work.journal'),{}
            except (ValueError,PermissionError):
                import sys
                return standardize_operator_result(operator_work_journal.result(str(sys.exception()),'clarification_required'),'work.journal'),{}
        if re.match(r'\s*(?:покажи|показать)\b',command,re.I) and re.search(r'на разбор',message,re.I):
            categories=[category for pattern,category in [('жалоб','complaint'),('пожелан','wish'),('иде[яию]','idea')]
                        if re.search(pattern,message,re.I)]
            args={'category':categories[0]} if len(categories)==1 else {}
            try:
                return standardize_operator_result(work_review.inbox_result(cursor,business_id,user_id,args),'work.journal'), {}
            except PermissionError:
                import sys
                return standardize_operator_result(operator_work_journal.result(str(sys.exception()),'blocked'),'work.journal'), {}
        args = directed_note(message)
        if args:
            blocked = operator_subscription_block(access, 'work.journal')
            if blocked:
                return blocked, {}
            saved = []
            message_id = next((r.get('id') for r in reversed(history or []) if r.get('role') == 'user'), None)
            key = str(payload.get('request_id') or message_id)
            tools = operator_work_journal.tools(cursor,business_id,user_id,channel,message,message_id,key,saved)
            tool = next(t for t in tools if t['name'] == 'work.save_observation')
            parts=re.split(r'(?<=\.)\s+(?=(?:Второй|Вторая|Третий|Третья)\b)',message,flags=re.I) if re.search(r'два замечания|две заметки|три замечания',message,re.I) else [message]
            for part in parts:
                note_args=directed_note(part) or {'quote':part,'category':'wish' if re.search(r'прос|хоч',part,re.I) else 'other','outcome':'note'}
                result = tool['execute'](note_args)
            if saved:
                result['status']='completed'
                entry = saved[-1]
                cursor.execute('SELECT user_id FROM business_work_reviewers WHERE business_id=%s AND enabled', (business_id,))
                reviewers = [r['user_id'] for r in cursor.fetchall()]
                permitted = any(work_review.can_review(cursor,business_id,u) for u in reviewers)
                result['chat_response'] = 'Сохранил на разбор: ' + message + '\nВладелец увидит запись.'
                result['chat_response'] += (' Управляющий с правом разбора также увидит её.' if permitted else ' Доступ администратора к разбору пока не настроен.')
                if entry.get('urgent'):
                    result['chat_response'] += ' Запись отмечена срочной; доставка уведомления пока не подтверждена.'
                result['journal_entries'] = saved
                href = '/dashboard/work-journal?business_id='+business_id+'&entry='+entry['id']
                result['result_ref'] = {'entity_id':entry['id'],'href':href,'label':'Открыть запись'}
                result['ui_actions'] = [{'action':'open_journal','label':label,'href':href+'&mode='+mode}
                                        for label,mode in [('Исправить запись','edit'),('Отменить запись','void')]]
            return standardize_operator_result(result,'work.journal'), {}
    if not re.search(r'^(?:измени|изменить|перепиши|переписать|переведи|перевести|придумай|напиши|замени|переделай|верни|восстанови)\b',command.strip(),re.I):
        return None
    if not re.search(r'этот пост|его\b|вместо него|этот текст|версию.{0,20}поста|второй пост|первый пост|третий пост',message,re.I):
        return None
    previous = next((r for r in reversed(history or []) if r.get('role') in {'operator','assistant'}), {})
    selected = (previous.get('result_json') or {}).get('selected_item')
    items=(previous.get('result_json') or {}).get('items') or []
    ordinal=re.search(r'\b(первый|второй|третий|четв[её]ртый|пятый)\s+пост',message,re.I)
    if ordinal:
        index={'первый':0,'второй':1,'третий':2,'четвертый':3,'четвёртый':3,'пятый':4}[ordinal[1].lower()]
        if index>=len(items) or (previous.get('result_json') or {}).get('resource')!='content':
            return standardize_operator_result(operator_editorial._result('В показанном списке нет такого поста. Сначала запросите нужные материалы.','clarification_required'),'content.item.edit'),{}
        row=items[index]
        current=operator_editorial._items(cursor,business_id,row.get('plan_id'),item_id=row.get('id'))
        if len(current)!=1:return standardize_operator_result(operator_editorial._result('Пост больше недоступен. Обновите список.','blocked'),'content.item.edit'),{}
        if str(row.get('updated_at') or '').replace(' ','T')!=str(current[0]['updated_at']).replace(' ','T'):
            return standardize_operator_result(operator_editorial._result('Пост изменился. Обновите список.','blocked'),'content.item.edit'),{}
        selected={'item_id':row['id'],'plan_id':row['plan_id'],'version':operator_editorial._version(current[0])}
    if not selected:
        items=(previous.get('result_json') or {}).get('items') or []
        if len(items)>1 and (previous.get('result_json') or {}).get('resource')=='content':
            return standardize_operator_result(operator_editorial._result(
                'Какой пост из показанного списка изменить? Назовите дату или тему.', 'clarification_required'), 'content.item.edit'), {
                    'capability':'content.editorial.clarification','source_message':message}
        return None
    blocked = operator_subscription_block(access,'content.item.edit')
    if blocked:
        return blocked, {}
    tool = {'name':'content.rewrite_item','capability':'content.item.edit','risk_class':'write_internal_draft',
            'input_schema':{'type':'object'},'deterministic_response':True,
            'execute':lambda args: (operator_editorial.restore_item if re.match(r'верни|восстанови',command,re.I) else operator_editorial.rewrite_item)(cursor,business_id,user_id,message,selected)}
    result = run_paid_operator_tool_loop(
        cursor,business_id=business_id,user_id=user_id,message=message,conversation_id=conversation_id,
        actor_context=actor,tools=[tool],planner=lambda state: ({'action':'error','message':state['observations'][-1].get('chat_response') or 'Не удалось изменить пост. Он остался прежним.','error_code':'operator_planner_failed'} if state['observations'] else {'action':'tool_call','tool':'content.rewrite_item','arguments':{}}))
    return standardize_operator_result(result,'content.item.edit'), {}


def photo_read_request(message):
    return bool(re.search(r'\b(?:покажи|показать|найди|посмотри|подбери)\b', message, re.I)
                and re.search(r'фото|изображени|\.(?:jpg|jpeg|png|webp)\b', message, re.I)
                and not re.search(r'\b(?:замени|прикрепи|поставь|используй|сохрани)\b', message, re.I))


def select_shown_photo(cursor, business_id, user_id, message, history):
    if not re.search(r'пусть\s+будет|выбир\w*|выбрал\w*|выбрала|используй|прикрепи|поставь|замени|добавь', message, re.I):
        return None
    if not re.search(r'фото|изображени|\.(?:jpg|jpeg|png|webp)\b', message, re.I):
        return None
    if re.search(r'не\s+(?:меняй|заменяй|прикрепляй|сохраняй|используй)\s+(?:(?:это|выбранное|текущее)\s+)?(?:фото|изображени)|пока\s+ничего|\bесли\b|\?', message, re.I):
        return None
    gallery = next((entry for entry in reversed(history or []) if (entry.get('result_json') or {}).get('photos')), None)
    if not gallery:
        return operator_editorial._result('Сначала покажите варианты фото для нужного поста.', 'clarification_required')
    photos = gallery['result_json']['photos']
    named = [photo for photo in photos if photo.get('name') and photo['name'].casefold() in message.casefold()]
    explicit_filename = re.search(r'\.(?:jpg|jpeg|png|webp)\b', message, re.I)
    if explicit_filename and not named:
        # An intervening search must not reinterpret an exact filename as the
        # same ordinal in a different gallery. Resolve only previously shown assets.
        for previous in reversed(history or []):
            previous_photos = (previous.get('result_json') or {}).get('photos') or []
            matches = [photo for photo in previous_photos if photo.get('name') and photo['name'].casefold() in message.casefold()]
            if matches:
                gallery, photos, named = previous, previous_photos, matches
                break
    number = re.match(r'\s*(\d+)\s*(?:[.)]|$)', message)
    chosen = named[0] if len(named) == 1 else (photos[int(number[1])-1] if not named and not explicit_filename and number and 0 < int(number[1]) <= len(photos) else None)
    if not chosen:
        return operator_editorial._result('Не удалось определить выбранное фото. Укажите имя файла из последнего списка.', 'clarification_required')
    if number and named and (int(number[1]) > len(photos) or int(number[1]) < 1 or photos[int(number[1])-1]['asset_id'] != chosen['asset_id']):
        return operator_editorial._result('Номер и имя файла относятся к разным фото. Укажите только точное имя файла.', 'clarification_required')
    selected = gallery['result_json'].get('selected_item')
    if not selected:
        selected = _photo_target(cursor, business_id, history)
        if selected:
            rows = operator_editorial._items(cursor, business_id, selected['plan_id'], item_id=selected['item_id'])
            try:
                viewed = datetime.fromisoformat(str(gallery.get('created_at')).replace('Z', '+00:00'))
                changed = datetime.fromisoformat(str(rows[0]['updated_at']).replace('Z', '+00:00'))
                if viewed.tzinfo is None:
                    viewed = viewed.replace(tzinfo=timezone.utc)
                if changed.tzinfo is None:
                    changed = changed.replace(tzinfo=timezone.utc)
                if changed > viewed:
                    return operator_editorial._result('Пост изменился после показа фото. Покажите его заново перед заменой.', 'blocked')
            except (ValueError, TypeError, IndexError):
                selected = None
    if not selected:
        return operator_editorial._result('Для какого поста сохранить выбранное фото? Назовите тему и дату.', 'clarification_required')
    return {'_photo_update':{**selected, 'photo_asset_id':chosen['asset_id']}}
