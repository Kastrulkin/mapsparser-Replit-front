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


def test_next_post_does_not_assume_moscow(daily):
    _, cursor = daily
    cursor.execute('DELETE FROM business_finance_settings')
    result = operator_core._read_requested_content(cursor, 'b', 'Покажи следующий пост')
    assert result['status'] == 'clarification_required'
    assert 'часовой пояс' in result['chat_response']


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
