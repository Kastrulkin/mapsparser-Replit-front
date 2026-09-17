"""Small, version-checked corrections to the most recent saved object."""
import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from services.operator_conversations import _row


def requested_date(cursor,business_id,message):
    iso=re.findall(r'\b20\d{2}-\d{2}-\d{2}\b',message)
    if iso:return date.fromisoformat(iso[-1])
    names={'понедельник':0,'вторник':1,'среду':2,'четверг':3,'пятницу':4,'субботу':5,'воскресенье':6}
    matches=[(match.start(),number) for name,number in names.items() for match in re.finditer(name,message,re.I)]
    relative=re.search(r'(?:сегодня|завтра|послезавтра)',message,re.I)
    if not matches and not relative:return None
    cursor.execute('SELECT timezone FROM business_finance_settings WHERE business_id=%s',(business_id,))
    timezone_name=_row(cursor,cursor.fetchone()).get('timezone')
    if not timezone_name:raise ValueError('Для переноса укажите точную дату или часовой пояс бизнеса.')
    today=datetime.now(ZoneInfo(timezone_name)).date()
    if matches:return today+timedelta(days=(max(matches)[1]-today.weekday())%7)
    return today+timedelta(days=2 if 'послезавтра' in message.lower() else 1 if 'завтра' in message.lower() else 0)


def route(cursor,*,business_id,user_id,channel,message,history,request_id):
    from services import operator_editorial,content_rules,work_journal
    previous=next((r for r in reversed(history or []) if r.get('role') in {'operator','assistant'}),{})
    result=previous.get('result_json') or {}
    if (result.get('selected_item') or result.get('rule_id')) and re.match(r'\s*(?:отмени |сделай |нет[, ]|перенеси|не завтра|выбери |давай |оставь |первый|второй|третий|[123] )',message,re.I):
        from services.operator_core import operator_subscription_block
        _,access=operator_editorial.authorize_actor(cursor,user_id,business_id)
        blocked=operator_subscription_block(access,'content.item.edit')
        if blocked:return blocked
    undo=bool(re.match(r'\s*отмени (?:последн.{0,6} )?(?:изменение|правку|правило|запись)',message,re.I))
    if undo and result.get('rule_id'):
        if re.match(r'\s*отмени правило',message,re.I):
            rule=content_rules.change(cursor,business_id=business_id,user_id=user_id,request_id=request_id,
                rule_id=result['rule_id'],expected_version=result.get('rule_version'),status='cancelled',source=channel)
        else:
            rule=content_rules.undo(cursor,business_id=business_id,user_id=user_id,request_id=request_id,
                rule_id=result['rule_id'],expected_version=result.get('rule_version'),source=channel)
        return operator_editorial._result('Последнее изменение правила отменено. '+('Действует: ' if rule['status']=='active' else 'Правило отменено: ')+rule['text'],rule_id=rule['id'],rule_version=rule['version'])
    entries=result.get('journal_entries') or []
    if undo and len(entries)==1:
        entry=entries[0]
        saved=work_journal.save_note(cursor,business_id,user_id,channel,None,request_id,message,
            {'id':entry['id'],'version':entry['version'],'void':True})
        return operator_editorial._result('Запись отменена. История сохранена.',capability='work.journal',journal_entries=[saved])
    selected=result.get('selected_item')
    choice=re.match(r'\s*(?:выбери |давай |оставь )?(первый|второй|третий|1|2|3) (?:вариант|пост)\b',message,re.I)
    if choice and not selected:
        items=result.get('items') or []
        number={'первый':0,'второй':1,'третий':2,'1':0,'2':1,'3':2}[choice[1].lower()]
        if result.get('resource')=='content' and len(items)>number:
            item=items[number]
            operator_editorial.authorize_actor(cursor,user_id,business_id)
            rows=operator_editorial._items(cursor,business_id,item.get('plan_id'),item_id=item.get('id'))
            if len(rows)==1:
                operator_editorial.authorize_actor(cursor,user_id,business_id)
                row=rows[0]
                return operator_editorial._result(str(row['scheduled_for'])+': '+row['theme']+'\n'+str(row.get('draft_text') or 'Текст ещё не подготовлен.'),
                    selected_item={'item_id':row['id'],'plan_id':row['plan_id'],'version':operator_editorial._version(row)})
        return None
    if not selected:return None
    if choice:
        operator_editorial.authorize_actor(cursor,user_id,business_id)
        rows=operator_editorial._items(cursor,business_id,selected.get('plan_id'),lock=True,item_id=selected['item_id'])
        if len(rows)!=1 or rows[0]['status'] not in operator_editorial.EDITABLE or rows[0]['plan_status']=='archived' or operator_editorial._version(rows[0])!=selected['version']:
            return operator_editorial._result('Пост изменился или недоступен. Откройте варианты заново.','blocked')
        row=rows[0];bundle=(row.get('metadata_json') or {}).get('content_generation_v2') or {}
        variants=bundle.get('variants') or []
        number={'первый':0,'второй':1,'третий':2,'1':0,'2':1,'3':2}[choice[1].lower()]
        if len(variants)<=number or not variants[number].get('quality_passed'):
            return operator_editorial._result('Такого готового варианта нет. Подготовить другой текст этого поста?','clarification_required')
        variant=variants[number]
        from services.operator_social_post_generation import _default_social_post_generator
        content_rules.validate(cursor,business_id,user_id,variant['text'],_default_social_post_generator)
        operator_editorial._change(cursor,row,row['theme'],row.get('goal'),user_id)
        cursor.execute("UPDATE contentplanitems SET draft_text=%s,status='edited',metadata_json=metadata_json||%s::jsonb,updated_at=clock_timestamp() WHERE id=%s AND business_id=%s",
            (variant['text'],json.dumps({'content_generation_v2':{**bundle,'selected_variant_id':variant['id']}}),row['id'],business_id))
        updated=operator_editorial._items(cursor,business_id,row['plan_id'],item_id=row['id'])[0]
        return operator_editorial._result('Выбран вариант '+str(number+1)+'. Черновик сохранён.\n'+variant['text'],
            selected_item={'item_id':row['id'],'plan_id':row['plan_id'],'version':operator_editorial._version(updated)})
    if undo:return operator_editorial.restore_item(cursor,business_id,user_id,message,selected)
    if re.match(r'\s*сделай (?:его |этот пост )?(?:короче|длиннее|теплее|живее)',message,re.I):
        return operator_editorial.rewrite_item(cursor,business_id,user_id,message,selected)
    if not re.match(r'\s*(?:нет[, ]|перенеси|не завтра|вместо .*пятниц)',message,re.I):return None
    target=requested_date(cursor,business_id,message)
    if not target:return None
    operator_editorial.authorize_actor(cursor,user_id,business_id)
    rows=operator_editorial._items(cursor,business_id,selected.get('plan_id'),lock=True,item_id=selected['item_id'])
    if len(rows)!=1:return operator_editorial._result('Пост недоступен. Выберите его заново.','blocked')
    row=rows[0]
    if row['status'] not in operator_editorial.EDITABLE or row['plan_status']=='archived' or operator_editorial._version(row)!=selected['version']:
        return operator_editorial._result('Пост изменился. Откройте его заново перед переносом.','blocked')
    metadata=dict(row.get('metadata_json') or {})
    history=list(metadata.get('operator_edit_history') or [])
    history.append({key:row.get(key) for key in ('theme','goal','draft_text','scheduled_for','status','usernews_id')})
    metadata['operator_edit_history']=history
    cursor.execute('UPDATE contentplanitems SET scheduled_for=%s,metadata_json=%s::jsonb,updated_at=clock_timestamp() WHERE id=%s AND business_id=%s',
        (target,json.dumps(metadata,default=str,ensure_ascii=False),row['id'],business_id))
    updated=operator_editorial._items(cursor,business_id,row['plan_id'],item_id=row['id'])[0]
    return operator_editorial._result('Перенёс пост на '+target.isoformat()+'. Текст сохранён.',
        selected_item={'item_id':row['id'],'plan_id':row['plan_id'],'version':operator_editorial._version(updated)})
