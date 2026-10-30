"""Deterministic dialogue stages shared by live and preview conversations."""
import re

STATES = {'greeting','clarify_need','service_selection','answer_question','booking_request',
          'waiting_for_staff','human_active','closing','needs_attention'}


def next_state(current, message, history=None):
    text = str(message).lower().replace('ё','е')
    if current in {'waiting_for_staff','human_active'}:
        return current
    if re.search(r'позов|жив\w* (человек|администратор|сотрудник)|(хочу|нужен|нужна).*(человек|администратор|сотрудник|оператор)|жалоб|возврат|противопоказ|беремен|аллерг|диагноз',text):
        return 'waiting_for_staff'
    if re.search(r'\b(запиши|запишите|записаться|перенеси|отмени)\b',text):
        # Without an accepted CRM route, booking intent goes to a human.
        return 'booking_request'
    if re.search(r'спасибо|до свидания|все понятно',text):
        return 'closing'
    if re.fullmatch(r'[\s!.,]*(здравствуйте|привет|добрый (день|вечер)|доброе утро)[\s!.,]*',text):
        return 'clarify_need'
    if re.search(r'сколько|цен[аыу]|стоим|длитель|минут|как проходит',text):
        return 'answer_question'
    from services.client_service_context import _terms
    if _terms(text):
        return 'service_selection'
    return 'clarify_need'


def preview_state(history, message):
    state='greeting'
    for item in (history or [])[-10:]:
        if item.get('role') in {'client','user'} or item.get('sender')=='client':
            state=next_state(state,item.get('content',''))
    return next_state(state,message)
