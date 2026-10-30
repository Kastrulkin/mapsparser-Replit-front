"""Deterministic dialogue stages shared by live and preview conversations."""
import re

STATES = {'greeting','clarify_need','service_selection','answer_question','booking_request',
          'waiting_for_staff','human_active','closing','needs_attention'}


RULES = [
    ('human_help', 'waiting_for_staff', 'Просьба человека, жалоба или безопасность', r'позов|жив\w* (человек|администратор|сотрудник)|(хочу|нужен|нужна).*(человек|администратор|сотрудник|оператор)|жалоб|возврат|противопоказ|беремен|аллерг|диагноз'),
    ('booking', 'booking_request', 'Запись, перенос или отмена', r'\b(запиши|запишите|записать|записаться|перенеси|перенесите|перенести|отмени|отмените|отменить)\b'),
    ('thanks', 'closing', 'Благодарность или прощание', r'спасибо|до свидания|все понятно'),
    ('greeting', 'clarify_need', 'Приветствие', r'^[\s!.,]*(здравствуйте|привет|добрый (день|вечер)|доброе утро)[\s!.,]*$'),
    ('question', 'answer_question', 'Цена, длительность или ход процедуры', r'сколько|цен[аыу]|стоим|длитель|минут|как проходит'),
]
STAFF_TRANSITIONS = {'accept':('waiting_for_staff','human_active','Сотрудник принял'),'close':('human_active','closing','Сотрудник завершил')}
LABELS = {'greeting':'Начало','clarify_need':'Уточнение','service_selection':'Подбор услуги','answer_question':'Ответ на вопрос','booking_request':'Пожелание записи','waiting_for_staff':'Очередь сотруднику','human_active':'Сотрудник подключился','closing':'Завершение','needs_attention':'Требует внимания'}


def next_state(current, message, history=None):
    text = str(message).lower().replace('ё','е')
    if current in {'waiting_for_staff','human_active'}:
        return current
    for key,target,label,pattern in RULES:
        if re.search(pattern,text):return target
    from services.client_service_context import _terms
    return 'service_selection' if _terms(text) else 'clarify_need'


def dialogue_graph():
    order=list(LABELS)
    positions={'greeting':(0,0),'clarify_need':(280,0),'service_selection':(560,0),'answer_question':(840,0),'booking_request':(840,210),'waiting_for_staff':(560,420),'human_active':(840,420),'closing':(1120,210),'needs_attention':(0,420)}
    edges=[]
    for source in order:
        if source in {'waiting_for_staff','human_active','booking_request'}:continue
        for key,target,label,pattern in RULES:
            edges.append({'id':source+':'+key,'source':source,'target':target,'label':label})
        for target,label in [('service_selection','Определена тема услуги'),('clarify_need','Нужно уточнение')]:
            edges.append({'id':source+':'+target,'source':source,'target':target,'label':label})
    for source,target,label in [('booking_request','waiting_for_staff','CRM не подключена'), *STAFF_TRANSITIONS.values()]:
        edges.append({'id':source+':'+target,'source':source,'target':target,'label':label})
    combined={}
    for edge in edges:
        key=edge['source']+':'+edge['target']
        if key in combined:combined[key]['label']+=' / '+edge['label']
        else:combined[key]={**edge,'id':key}
    edges=list(combined.values())
    return {'nodes':[{'id':key,'label':LABELS[key],'x':positions[key][0],'y':positions[key][1],'reachable':key!='needs_attention'} for key in order], 'edges':edges,'rule_order':[rule[0] for rule in RULES], 'rules':[{'id':key,'target':target,'label':label} for key,target,label,pattern in RULES], 'note':'Правила проверяются сверху вниз. Требует внимания зарезервирован, автоматического входа сейчас нет.'}


def preview_state(history, message):
    state='greeting'
    for item in (history or [])[-10:]:
        if item.get('role') in {'client','user'} or item.get('sender')=='client':
            state=next_state(state,item.get('content',''))
    return next_state(state,message)
