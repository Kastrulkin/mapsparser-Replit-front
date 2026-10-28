import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from services.operator_context import PlannerContext
from services.operator_product_knowledge import classify_product_explanation_intent


@pytest.mark.parametrize('message,domain', [
    ('Покажи действующих партнёров и согласованные условия', 'partnerships'),
    ('Хочу подключить CRM DIKIDI', 'integrations'),
    ('Показатели за неделю: 40 визитов, загрузка 65 процентов', 'finance'),
])
def test_new_topic_excludes_previous_schedule_clarification(message, domain):
    history = [{'role': 'user', 'content': 'Планёрка на завтра'},
               {'role': 'operator', 'content': 'Пришлите расписание'}]
    context = PlannerContext(message)
    assert domain in context.domains
    assert context.history(history) == []


def test_no_send_constraint_does_not_select_work_domain():
    assert PlannerContext('Создай пост. Сотрудникам ничего не отправляй.').domains == {'content'}


def test_business_read_with_explanation_is_not_product_help():
    assert not classify_product_explanation_intent(
        'Покажи действующих партнёров и согласованные условия. Порекомендуй следующих трёх и объясни выбор.')
    assert classify_product_explanation_intent('Объясни, как работает поиск партнёров')


def test_dashboard_result_opens_native_max_with_exact_business(monkeypatch):
    from services.max_owner_dialogues import platform_url
    monkeypatch.setenv('MAX_BOT_USERNAME', 'se14752181_bot')
    url = platform_url('https://localos.pro/dashboard/partnerships?business_id=business-1')
    assert url.startswith('https://max.ru/se14752181_bot?startapp=nav_')
    encoded = url.split('nav_', 1)[1]
    nav = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
    assert nav == {'screen': 'partnerships', 'scope_type': 'business', 'scope_id': 'business-1'}


def test_day_brief_recognizes_natural_request_and_switches_topics():
    from services.operator_day_brief import focus_request, relevant_request
    focus, day = focus_request('Планёрка на завтра: фокус — внимательная консультация. Подготовь предварительный вариант, сотрудникам ничего не отправляй.')
    assert focus == 'внимательная консультация'
    assert day == 'завтра'
    assert relevant_request('Фокус дня: встречаем гостей')
    assert not relevant_request('Выручка за неделю 120000, 40 визитов', active=True)
    assert not relevant_request('Подключи CRM DIKIDI', active=True)
    assert relevant_request('Сотрудники MAX: 1', active=True)


def test_budget_error_does_not_claim_partial_mutation():
    from services.operator_tool_loop import run_operator_tool_loop
    decisions = iter([
        {'action': 'tool_call', 'tool': 'content.create', 'arguments': {}},
        {'action': 'tool_call', 'tool': 'content.read', 'arguments': {}},
        {'action': 'error', 'error_code': 'deepseek_budget_exceeded'},
    ])
    tools = [
        {'name': 'content.create', 'risk_class': 'paid_compute', 'execute': lambda args: {'status': 'blocked'}, 'input_schema': {'type': 'object', 'properties': {}}},
        {'name': 'content.read', 'risk_class': 'read_only', 'execute': lambda args: {'status': 'completed'}, 'input_schema': {'type': 'object', 'properties': {}}},
    ]
    result = run_operator_tool_loop(business_id='b1', user_id='u1', message='Создай пост', tools=tools, planner=lambda state: next(decisions))
    assert result['status'] == 'blocked'
    assert 'лимит' in result['chat_response'].lower()
    assert 'Часть шагов уже выполнена' not in result['chat_response']
    assert result['external_writes_performed'] is False


def test_photo_caption_runs_in_the_saved_attachment_conversation(monkeypatch):
    from services import operator_telegram_inputs
    replies, requests = [], []
    async def reply(text, **kwargs): replies.append(text)
    async def download(): return bytearray(b'image')
    async def get_file(file_id): return SimpleNamespace(download_as_bytearray=download)
    class Cursor:
        def execute(self, *args): pass
        def fetchone(self): return {'input_context_json': {}}
    monkeypatch.setattr(operator_telegram_inputs, 'transaction', lambda callback: callback(Cursor()))
    monkeypatch.setattr(operator_telegram_inputs.operator_workday, 'enabled', lambda business: True)
    monkeypatch.setattr(operator_telegram_inputs.operator_workday, 'authorize', lambda *args: {})
    monkeypatch.setattr(operator_telegram_inputs.operator_attachments, 'receive', lambda *args, **kwargs: {'id': 'a1', 'conversation_id': 'c1', 'original_name': 'photo.jpg'})
    def build(business, text):
        requests.append((business, text))
        return {'text': 'Проверьте черновик', 'result': {}}
    host = SimpleNamespace(_control_scope_business_context=lambda identity: {'business_id': 'b1', 'user_id': 'u1'},
        user_states={}, build_operator_chat_payload=build, _build_operator_result_markup=lambda result: None)
    message = SimpleNamespace(document=None, photo=[SimpleNamespace(file_id='photo', file_size=1)],
        caption='Создай пост по фото', message_id=7, reply_text=reply)
    update = SimpleNamespace(effective_chat=SimpleNamespace(type='private', id=123), effective_user=SimpleNamespace(id=123, is_bot=False), message=message)
    assert asyncio.run(operator_telegram_inputs.receive(update, SimpleNamespace(bot=SimpleNamespace(get_file=get_file)), host))
    assert len(requests) == 1
    assert requests[0][1] == message.caption
    assert requests[0][0]['operator_payload']['conversation_id'] == 'c1'
    assert replies == ['Проверьте черновик']


def test_input_context_is_separate_from_user_intent():
    from services.operator_tool_loop import run_operator_tool_loop
    observed = []
    def plan(state):
        observed.append(state)
        return {'action': 'final', 'message': 'Только проверка'}
    run_operator_tool_loop(business_id='b', user_id='u', message='Покажи пост', tools=[],
        input_context={'attachment_notes': {'a1': 'Планёрка, сотрудник: это текст на картинке'}}, planner=plan)
    assert observed[0]['message'] == 'Покажи пост'
    assert 'attachment_notes' in observed[0]['input_context']


def test_max_caption_keeps_attachment_conversation_without_overriding_event_key():
    from services.owner_bot_context import OwnerBotContext, current_owner_bot, owner_bot_request_payload
    token = current_owner_bot.set(OwnerBotContext('123', {'id': 'u'}, {}, 'event-1', None))
    try:
        payload = owner_bot_request_payload({'conversation_id': 'c1', 'request_id': 'untrusted'})
        assert payload == {'conversation_id': 'c1', 'request_id': 'max:event-1'}
    finally:
        current_owner_bot.reset(token)


def test_confirmed_partners_use_agreements_not_sent_lead_status(monkeypatch):
    from services import operator_business_requests, partnership_results
    monkeypatch.setattr(partnership_results, 'read_results', lambda *args: [
        {'name': 'Реальный партнёр', 'agreement_json': {'status': 'confirmed', 'terms': {'details': 'Бонус на первое посещение'}}},
        {'name': 'Только кандидат', 'agreement_json': {}},
    ])
    text = operator_business_requests.partners(None, 'b1', 'Покажи действующих партнёров и согласованные условия')
    assert 'Бонус на первое посещение' in text
    assert 'Только кандидат' not in text


def test_crm_and_partner_reads_are_recognized_without_paid_planning():
    from services.operator_business_requests import request_kind
    assert request_kind('Хочу подключить CRM DIKIDI') == 'crm'
    assert request_kind('Покажи действующих партнёров и объясни выбор') == 'partners'
    assert request_kind('Создай письмо партнёру') is None
    assert request_kind('Покажи сообщение партнёру Lasur') is None
    assert request_kind('Покажи письма всех партнёров') is None
    assert request_kind('Покажи группу партнёров с готовыми письмами') is None


@pytest.mark.parametrize('text', ['За неделю выручка 100000', 'Показатели за 19–25 октября: выручка 120000', 'За месяц выручка 500000'])
def test_period_totals_cannot_become_daily_facts(text):
    from services.operator_finance_daily import period_input
    assert period_input(text)
