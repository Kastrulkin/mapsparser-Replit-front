"""Deterministic handling of explicit follow-ups and addressed work notes."""
import re
from services import operator_editorial, operator_work_journal, work_journal, work_review


def remember_selection(cursor, business_id, result):
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
    category = ('complaint' if re.search(r'недоволь|жалоб|плохо встрет', message, re.I) else
                'wish' if re.search(r'пожелани|хотелось бы|клиент.{0,20}прос', message, re.I) else
                'idea' if re.search(r'идея|предлагаю', message, re.I) else None)
    if category == 'complaint' and re.search(r'\b(?:возможно|может|будет)\b|была бы|был бы',message,re.I):
        return None
    return {'quote': message, 'category': category, 'outcome': 'note'} if category else None


def route(cursor, *, business_id, user_id, channel, message, history, conversation_id, payload, actor, access):
    from services.operator_core import standardize_operator_result, operator_subscription_block
    from services.operator_tool_billing import run_paid_operator_tool_loop
    from services import operator_voice_followups
    try:
        corrected=operator_voice_followups.route(cursor,business_id=business_id,user_id=user_id,channel=channel,
            message=message,history=history,request_id=str(payload.get('request_id') or conversation_id)+':correction')
    except (ValueError,PermissionError):
        import sys
        corrected={'status':'clarification_required','chat_response':str(sys.exception())}
    if corrected is not None:
        return standardize_operator_result(corrected,'content.item.edit'), {}
    if work_journal.enabled(business_id):
        if re.match(r'\s*(?:покажи|показать)\b',message,re.I) and re.search(r'на разбор',message,re.I):
            categories=[category for pattern,category in [('жалоб','complaint'),('пожелан','wish'),('иде[яию]','idea')]
                        if re.search(pattern,message,re.I)]
            args={'category':categories[0]} if len(categories)==1 else {}
            return standardize_operator_result(work_review.inbox_result(cursor,business_id,user_id,args),'work.journal'), {}
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
            result = tool['execute'](args)
            if saved:
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
    if not re.search(r'^(?:измени|изменить|перепиши|переписать|придумай|напиши|замени|переделай)\b',message.strip(),re.I):
        return None
    if not re.search(r'этот пост|его\b|вместо него|этот текст',message,re.I):
        return None
    previous = next((r for r in reversed(history or []) if r.get('role') in {'operator','assistant'}), {})
    selected = (previous.get('result_json') or {}).get('selected_item')
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
            'execute':lambda args: operator_editorial.rewrite_item(cursor,business_id,user_id,message,selected)}
    result = run_paid_operator_tool_loop(
        cursor,business_id=business_id,user_id=user_id,message=message,conversation_id=conversation_id,
        actor_context=actor,tools=[tool],planner=lambda state: ({'action':'error','message':state['observations'][-1].get('chat_response') or 'Не удалось изменить пост. Он остался прежним.','error_code':'operator_planner_failed'} if state['observations'] else {'action':'tool_call','tool':'content.rewrite_item','arguments':{}}))
    return standardize_operator_result(result,'content.item.edit'), {}
