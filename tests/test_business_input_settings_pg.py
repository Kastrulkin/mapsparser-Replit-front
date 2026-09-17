import pytest
from tests.test_operator_voice_pg import pg
from tests.test_finance_daily_pg import daily
from services import business_input_settings, finance_daily, operator_core, operator_audio


def test_settings_shared_and_conflicts_need_confirmation(daily):
    _, cursor = daily
    cursor.execute('ALTER TABLE businesses ADD COLUMN currency TEXT, ADD COLUMN timezone TEXT')
    cursor.execute("UPDATE businesses SET currency='RUB',timezone='Europe/Moscow'")
    before = business_input_settings.resolve(cursor, 'b')
    assert before['currency'] is None and before['timezone'] is None
    assert set(before['conflicts']) == {'currency', 'timezone'}
    preview = finance_daily.prepare(cursor, 'b', 'u', {'kind': 'settings', 'currency': 'EUR', 'timezone': 'Europe/Tallinn'}, 'web', 'm')
    finance_daily.apply(cursor, 'b', 'u', preview, 'settings-action')
    saved = business_input_settings.resolve(cursor, 'b')
    assert saved['currency'] == 'EUR' and saved['timezone'] == 'Europe/Tallinn'
    assert saved['conflicts'] == []
    with pytest.raises(ValueError, match='изменились'):
        finance_daily.apply(cursor, 'b', 'u', preview, 'other-action')


def test_missing_settings_ask_once_then_preview_preserves_original(daily, monkeypatch):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    first, pending = business_input_settings.route_setup(cursor, 'b', 'u', 'telegram', 'Сегодня 10 продаж', {}, 'c', None)
    assert first['status'] == 'clarification_required'
    assert pending['source_message'] == 'Сегодня 10 продаж'
    captured = []
    def prepare(**kwargs):
        captured.append(kwargs)
        return {'status': 'approval_required', 'approval': {'envelope': {}}}
    monkeypatch.setattr(operator_core, '_prepare_registered_capability_approval', prepare)
    preview, _ = business_input_settings.route_setup(cursor, 'b', 'u', 'telegram', 'EUR, Europe/Tallinn', pending, 'c', None)
    assert preview['approval']['envelope']['resume_message'] == 'Сегодня 10 продаж'
    assert captured[0]['payload']['data'] == {'currency': 'EUR', 'timezone': 'Europe/Tallinn'}
    assert not business_input_settings.resolve(cursor, 'b')['currency']


def test_employee_cannot_set_business_defaults(daily, monkeypatch):
    _, cursor = daily
    monkeypatch.setattr(operator_audio, 'authorize_actor', lambda *args: ({'role': 'business_user'}, {}))
    with pytest.raises(PermissionError, match='владелец'):
        finance_daily.prepare(cursor, 'b', 'u', {'kind': 'settings', 'currency': 'EUR', 'timezone': 'UTC'}, 'web', 'm')


@pytest.mark.parametrize('message', ['Покажи следующий пост', 'Когда следующий пост', 'Покажи контент план'])
def test_content_read_without_business_defaults(daily, monkeypatch, message):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    from services import operator_query
    monkeypatch.setattr(operator_core, '_operator_tool_loop_enabled', lambda: False)
    monkeypatch.setattr(operator_query, '_load_module_items', lambda *args, **kwargs: ([
        {'title': 'Опубликован', 'scheduled_for': '2020-01-01', 'status': 'published'},
        {'title': 'Первый по плану', 'scheduled_for': '2020-01-02', 'status': 'edited'},
        {'title': 'Позже', 'scheduled_for': '2099-01-01', 'status': 'planned'},
    ], {}))
    assert operator_core._content_read_request(message)
    for channel in ['web', 'telegram', 'telegram_mini_app']:
        result, pending = operator_core.route_operator_message(cursor, business_id='b', user_id='u',
            channel=channel, message=message, pending_context={'capability': 'settings.input',
                'required_fields': ['currency', 'timezone']})
        assert result['status'] == 'completed'
        assert result['items'][0]['title'] == 'Первый по плану'
        assert result['query']['filters'] == []
        assert not result['external_writes_performed']
        assert pending == {}


@pytest.mark.parametrize('day_changed', [False, True])
def test_settings_confirmation_resumes_once_and_keeps_finance_confirmation(daily, monkeypatch, day_changed):
    conn, cursor = daily
    from services.operator_conversations import get_or_create_operator_conversation, create_pending_operator_action
    conversation = get_or_create_operator_conversation(cursor, business_id='b', user_id='u', channel='web')
    action = create_pending_operator_action(cursor, conversation_id=conversation['id'], business_id='b', user_id='u',
        capability='settings.input', envelope={'orchestrator_action_id': 'settings-orchestrator',
            'resume_message': 'Сегодня 10 продаж', 'resume_channel': 'web', 'resume_conversation_id': conversation['id'],
            'resume_received_at': '2000-01-01T23:59:00+00:00' if day_changed else None})
    conn.commit()
    calls = []
    def router(c, **kwargs):
        calls.append(kwargs['message'])
        return {'status': 'approval_required', 'capability': 'finance.daily.write', 'chat_response': 'Сохранить итог?',
                'approval': {'envelope': {'orchestrator_action_id': 'finance-orchestrator'}}}, {}
    monkeypatch.setattr(operator_core, 'route_operator_message', router)
    class ApprovedSettings:
        def resolve_human_decision(self, *args, **kwargs):
            return {'success': True, 'status': 'completed', 'result': {'status': 'completed', 'chat_response': 'Настройки сохранены'}}
    first, _ = operator_core.confirm_pending_operator_action(cursor, action_id=action['id'], business_id='b', user_id='u', action_orchestrator=ApprovedSettings())
    conn.commit()
    second, repeated = operator_core.confirm_pending_operator_action(cursor, action_id=action['id'], business_id='b', user_id='u', action_orchestrator=ApprovedSettings())
    assert repeated
    if day_changed:
        assert calls == []
        assert first['status'] == second['status'] == 'clarification_required'
    else:
        assert calls == ['Сегодня 10 продаж']
        assert first['status'] == second['status'] == 'approval_required'
        assert first['approval']['action_id'] != action['id']


@pytest.mark.parametrize('message', ['У Riderra есть неотвеченные отзывы', 'Какое время работы сейчас указано', 'Покажи контент план', 'Подготовь пост про Пхукет'])
def test_settings_do_not_capture_unrelated_task(daily, monkeypatch, message):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    old = {'capability': 'settings.input', 'source_message': 'Когда следующий пост', 'settings': {}}
    assert business_input_settings.route_setup(cursor, 'b', 'u', 'telegram', message, old, 'c', None) is None


def test_scheduling_still_requires_timezone(daily, monkeypatch):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    response, pending = business_input_settings.route_setup(cursor, 'b', 'u', 'web', 'Опубликуй пост завтра в 10', {}, 'c', None)
    assert pending['required_fields'] == ['timezone']


@pytest.mark.parametrize('channel', ['web', 'telegram', 'telegram_mini_app'])
@pytest.mark.parametrize('text', ['Поставь город Пхукет и валюту баты', 'Сохрани настройки бизнеса: город: Пхукет; валюта: THB'])
def test_city_currency_preview_and_confirm(daily, monkeypatch, channel, text):
    _, cursor = daily
    cursor.execute('ALTER TABLE business_finance_settings ADD COLUMN city TEXT')
    def prepare(**kwargs):
        return {'status': 'approval_required', 'approval': {'envelope': {}}, 'payload': kwargs['payload']}
    monkeypatch.setattr(operator_core, '_prepare_registered_capability_approval', prepare)
    result, _ = business_input_settings.route_setup(cursor, 'b', 'u', channel, text, {}, 'c', None)
    assert result['payload']['data'] == {'city': 'Пхукет', 'currency': 'THB', 'timezone': 'Asia/Bangkok'}
    assert business_input_settings.resolve(cursor, 'b')['timezone'] == 'Europe/Tallinn'
    finance_daily.apply(cursor, 'b', 'u', result['payload'], 'set-city')
    finance_daily.apply(cursor, 'b', 'u', result['payload'], 'set-city')
    saved = business_input_settings.resolve(cursor, 'b')
    assert saved['city'] == 'Пхукет' and saved['timezone'] == 'Asia/Bangkok' and saved['currency'] == 'THB'
    cursor.execute("SELECT count(*) n FROM finance_daily_events WHERE action_id='set-city'")
    assert cursor.fetchone()['n'] == 1


@pytest.mark.parametrize('patch', [{'currency': 'EUR'}, {'timezone': 'Europe/Tallinn'}])
def test_partial_settings_without_inventing_other_fields(daily, patch):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    prepared = finance_daily.prepare(cursor, 'b', 'u', {'kind': 'settings', **patch}, 'web', 'm')
    finance_daily.apply(cursor, 'b', 'u', prepared, 'partial')
    saved = business_input_settings.resolve(cursor, 'b')
    for field in ['currency', 'timezone']:
        assert saved[field] == patch.get(field)


def test_unknown_city_does_not_keep_previous_timezone(daily, monkeypatch):
    _, cursor = daily
    response, pending = business_input_settings.route_setup(cursor, 'b', 'u', 'web', 'Установи город Спрингфилд', {}, 'c', None)
    assert response['status'] == 'clarification_required'
    assert 'timezone' in pending['required_fields']
    with pytest.raises(ValueError, match='нового города'):
        finance_daily.prepare(cursor, 'b', 'u', {'kind': 'settings', 'city': 'Спрингфилд'}, 'web', 'm')


def test_city_settings_migration_is_repeatable(daily, monkeypatch):
    import importlib.util
    from pathlib import Path
    from alembic import op
    _, cursor = daily
    monkeypatch.setattr(op, 'execute', cursor.execute)
    spec = importlib.util.spec_from_file_location('city_migration', Path('alembic_migrations/versions/20260914_business_input_city.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade(); module.upgrade()
    cursor.execute('SELECT city FROM business_finance_settings')
    assert cursor.fetchone()['city'] is None


@pytest.mark.parametrize('message', ['Сохрани пост про город Таллин', 'Как установить город Таллин и валюту евро?', 'Например, город Таллин, валюта евро'])
def test_content_and_examples_are_not_settings_writes(daily, message):
    _, cursor = daily
    assert business_input_settings.route_setup(cursor, 'b', 'u', 'web', message, {}, 'c', None) is None


def test_explicit_reply_resumes_original_command(daily, monkeypatch):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    _, pending = business_input_settings.route_setup(cursor, 'b', 'u', 'web', 'Опубликуй пост завтра в 10', {}, 'c', None)
    monkeypatch.setattr(operator_core, '_prepare_registered_capability_approval', lambda **kwargs: {'status':'approval_required','approval':{'envelope':{}}})
    result, _ = business_input_settings.route_setup(cursor, 'b', 'u', 'web', 'Установи город Таллин', pending, 'c', None)
    assert result['approval']['envelope']['resume_message'] == 'Опубликуй пост завтра в 10'


def test_full_router_leaves_settings_for_reviews(daily, monkeypatch):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    monkeypatch.setattr(operator_core, '_operator_tool_loop_enabled', lambda: False)
    from services import operator_query
    monkeypatch.setattr(operator_query, 'execute_operator_query', lambda *args, **kwargs: {'status':'completed','capability':'operator.query','chat_response':'Есть отзывы без ответа'})
    result, pending = operator_core.route_operator_message(cursor, business_id='b', user_id='u', channel='telegram', message='Покажи отзывы без ответа', pending_context={'capability':'settings.input','source_message':'Когда следующий пост'})
    assert result['status'] == 'completed'
    assert result['capability'] != 'settings.input'
    assert pending == {}


@pytest.mark.parametrize('allowed', [False, True])
def test_settings_endpoint_checks_business_access(daily, monkeypatch, allowed):
    from flask import Flask, Blueprint
    from api import operator_input_settings_api
    _, cursor = daily
    class ReadConnection:
        def cursor(self): return cursor
    class ReadDatabase:
        conn = ReadConnection()
        def rollback_and_close(self): pass
    monkeypatch.setattr(operator_input_settings_api, 'DatabaseManager', ReadDatabase)
    monkeypatch.setattr(operator_input_settings_api, 'require_auth_from_request', lambda: {'user_id':'u'})
    monkeypatch.setattr(operator_input_settings_api, 'verify_business_access', lambda *args: (allowed, 'u'))
    app = Flask(__name__)
    bp = Blueprint('settings_test', __name__)
    operator_input_settings_api.register_input_settings_routes(bp)
    app.register_blueprint(bp)
    response = app.test_client().get('/input-settings?business_id=b')
    assert response.status_code == (200 if allowed else 403)
    if allowed:
        assert response.json['timezone'] == 'Europe/Tallinn'
    else:
        assert 'timezone' not in response.json


@pytest.mark.parametrize('amount', ['350 р', '350 ₽', '350 EUR', '350 руб.', '350 рублей'])
@pytest.mark.parametrize('channel', ['web', 'telegram_mini_app', 'telegram'])
def test_audited_finance_explicit_currency_does_not_ask_for_default(daily, monkeypatch, amount, channel):
    _, cursor = daily
    cursor.execute("UPDATE business_finance_settings SET currency=NULL")
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    message = 'Сегодня 10 чеков, выручка ' + amount
    assert 'currency' not in business_input_settings.required_settings(message)
    assert business_input_settings.route_setup(cursor, 'b', 'u', channel, message, {}, 'c', None) is None


@pytest.mark.parametrize('message', [
    'Что предложить клиентам сегодня? Составь план допродаж для администратора.',
    'Клиент отказался от допродажи, передай руководителю.',
    'Составь чеклист встречи клиента.',
    'Как оформить возврат клиенту?',
    'Как записать расход?',
    'Подскажи, как увеличить продажи',
    'Клиентка попросила возврат, передай руководителю.',
    'Клиент пожаловался на ошибку в чеке вчера. Передай администратору.',
])
def test_recommendations_and_notes_do_not_require_currency(daily, monkeypatch, message):
    _, cursor = daily
    cursor.execute("UPDATE business_finance_settings SET currency=NULL")
    monkeypatch.setenv('OPERATOR_REQUEST_AUDIT_BUSINESS_IDS', 'b')
    assert 'currency' not in business_input_settings.required_settings(message)
    assert business_input_settings.route_setup(cursor, 'b', 'u', 'web', message, {}, 'c', None) is None
